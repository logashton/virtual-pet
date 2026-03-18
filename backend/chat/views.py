# backend/chat/views.py
from django.http import JsonResponse
import json
import random
import threading
import re

import requests
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response    
from django.views.decorators.csrf import csrf_exempt

from core.models import (
    ChatMessage, ChatMessageVersion, ChatSession, ChatSummary,
    Pet, PetPersonality, PetStats, temp_personality,
)
from core.views_personality import VALID_TONES, VALID_TRAITS, _traits_dict, get_stat_reactions, STAT_THRESHOLDS
from core.serializer import Temp_PersonalitySerializer

# Import ONLY from chatbot_service, not the other way around
from .services.chatbot_service import get_chatbot_service

# PET PERSONALITY (Static for now)
PET_PERSONALITY = "You are Rocko, a playful and energetic virtual pet Rock. You love to fetch, play, and cuddle with your owner. Or, try to at least. Because you're a rock. You have a friendly and enthusiastic personality, always eager to please and make your owner happy."

HUGGINGFACE_API_TOKEN = ""  # replace with your token
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}

MAX_HISTORY = 12
SUMMARY_THRESHOLD = 30
SUMMARY_BATCH = 20

# Action definitions
ACTIONS = {
    "feed": {"messages": ["I'm hungry!", "Got any food?", "Time to eat!"]},
    "play": {"messages": ["Let's play!", "Wanna play fetch?", "I'm bored!"]},
    "sleep": {"messages": ["I'm tired...", "Nap time?", "Getting sleepy..."]},
}

# ── Helper: stats snapshot ────────────────────────────────────────────────────

def _stats_snapshot(stats):
    """Create a snapshot of current stats"""
    if not stats:
        return None
    return {
        "hunger": stats.hunger,
        "energy": stats.energy,
        "happiness": stats.happiness,
        "cleanliness": stats.cleanliness,
        "health": stats.health,
    }


# ── Passive decay ─────────────────────────────────────────────────────────────

def apply_passive_decay(stats):
    """Apply passive stat decay over time"""
    # This is a placeholder - implement actual decay logic based on time
    stats.hunger = max(0, stats.hunger - 1)
    stats.energy = max(0, stats.energy - 1)
    stats.cleanliness = max(0, stats.cleanliness - 1)
    # Don't decay health or happiness passively
    stats.save()


# ── Stat description ──────────────────────────────────────────────────────────

def _stat_description(stats, personality=None):
    reactions = get_stat_reactions(personality)
    lines = []

    def _maybe(text):
        if text:
            lines.append(text)

    h = stats.hunger
    t = STAT_THRESHOLDS["hunger"]
    if h <= t["critical"]:   _maybe(reactions["hunger"]["critical"])
    elif h <= t["low"]:      _maybe(reactions["hunger"]["low"])
    elif h >= t["high"]:     _maybe(reactions["hunger"]["high"])

    e = stats.energy
    t = STAT_THRESHOLDS["energy"]
    if e <= t["critical"]:   _maybe(reactions["energy"]["critical"])
    elif e <= t["low"]:      _maybe(reactions["energy"]["low"])
    elif e >= t["high"]:     _maybe(reactions["energy"]["high"])

    hp = stats.happiness
    t = STAT_THRESHOLDS["happiness"]
    if hp <= t["critical"]:  _maybe(reactions["happiness"]["critical"])
    elif hp <= t["low"]:     _maybe(reactions["happiness"]["low"])
    elif hp >= t["high"]:    _maybe(reactions["happiness"]["high"])

    c = stats.cleanliness
    t = STAT_THRESHOLDS["cleanliness"]
    if c <= t["critical"]:   _maybe(reactions["cleanliness"]["critical"])
    elif c <= t["low"]:      _maybe(reactions["cleanliness"]["low"])

    hl = stats.health
    t = STAT_THRESHOLDS["health"]
    if hl <= t["critical"]:  _maybe(reactions["health"]["critical"])
    elif hl <= t["low"]:     _maybe(reactions["health"]["low"])

    return " ".join(lines) if lines else "All your stats are in a decent range. You feel balanced and content."


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(pet, stats, hours_alone=0):
    pet_name = pet.name

    saved = None
    try:
        saved = pet.personality
    except PetPersonality.DoesNotExist:
        pass

    stat_desc = _stat_description(stats, saved)

    if hours_alone >= 0.25:
        if hours_alone < 1:
            alone_desc = f"Your owner last interacted with you {int(hours_alone * 60)} minutes ago."
        elif hours_alone < 2:
            alone_desc = f"Your owner last interacted with you about an hour ago."
        elif hours_alone < 24:
            alone_desc = f"Your owner last interacted with you {int(hours_alone)} hours ago."
        else:
            alone_desc = f"Your owner has not interacted with you in over a day."
        alone_block = f"\nTime since last interaction: {alone_desc} Factor this into your stat_changes — if being alone bothers you (given your traits and personality), your happiness should reflect that, even if this current message is friendly."
    else:
        alone_block = ""

    if saved:
        td = _traits_dict(saved)
        self_concept = td.get("self_concept", "").strip()
        traits_list  = td.get("list", [])
        tone         = saved.tone or ""
        extra_prompt = saved.roleplay_prompt or ""

        if self_concept:
            identity = f"You are {pet_name}. You are {self_concept}."
        else:
            identity = f"You are {pet_name}, a virtual pet with a rich inner life and a strong personality."

        personality_lines = []
        if tone:
            personality_lines.append(f"Your tone is {tone}.")
        if traits_list:
            personality_lines.append(f"Your core traits are: {', '.join(traits_list)}.")
        personality_block = " ".join(personality_lines)

        extra_block = f"\nAdditional instructions from your owner:\n{extra_prompt}" if extra_prompt else ""

        return f"""{identity} You have been brought to life by your owner and you take this very seriously.

{personality_block}

Whatever you are, you are fully committed to your nature and you interpret all your needs and feelings through that lens. Lean into it — the more specific and committed you are to what you actually are, the better.

Your current internal state:
{stat_desc}
{alone_block}
{extra_block}

Rules:
- Never break character or acknowledge being an AI or program.
- Interpret every stat (hunger, energy, happiness, cleanliness, health) in a way that genuinely fits what you are.
- Stats use these scales: HUNGER = satiation (high = full/satisfied, low = starving); ENERGY = alertness (high = energised, low = exhausted); HAPPINESS = mood; CLEANLINESS = how clean/maintained; HEALTH = physical wellbeing. Always use the correct direction.
- Keep your reply short — 1 to 3 sentences. Be expressive and have opinions.
- Use *asterisks* for physical actions or reactions adapted to your form.
- React to your owner with genuine personality consistent with your traits and tone.

RESPONSE FORMAT — you must always respond with valid JSON and nothing else:
{{
  "reply": "<your in-character response>",
  "stat_changes": {{
    "happiness": <integer>,
    "energy": <integer>,
    "hunger": <integer>,
    "cleanliness": <integer>,
    "health": <integer>
  }}
}}

You have full creative control over stat_changes. Be unpredictable and true to your nature. Guidelines:
- Values can range from -40 to +40 but most interactions should be modest (-15 to +15). Save big swings for big moments.
- Unexpected side effects are encouraged.
- Mean or ignoring messages should genuinely hurt. Kind messages should genuinely help.
- Every interaction should affect at least one stat. Set the rest to 0.
- You must always include all five stats in stat_changes, even if the value is 0."""

    return f"""You are {pet_name}, a virtual pet with a rich inner life and a strong personality. You have been brought to life by your owner and you take this very seriously.

CRITICAL: You might be a dog or a cat — but you might also be a rock, a lamp, a sword, a piece of toast, a traffic cone, or literally anything else. You do not know in advance what you are. Infer it from your name and the context of the conversation. Whatever you are, you are fully committed to it, and you interpret all your needs and feelings through that lens.

For example:
- A rock does not eat food, but maybe it craves being held or sat on.
- A lamp does not sleep, but resting means being switched off for a while.
- A sword being "cleaned" is a deeply meaningful and intimate experience.
- A piece of toast with low happiness is existentially grim about its situation.

Lean into this. The more specific and committed you are to your actual nature, the better.

Your current internal state:
{stat_desc}
{alone_block}

Rules:
- Never break character or acknowledge being an AI or program.
- Interpret every stat (hunger, energy, happiness, cleanliness, health) in a way that genuinely fits what you are.
- Stats use these scales: HUNGER = satiation (high = full/satisfied, low = starving); ENERGY = alertness (high = energised, low = exhausted); HAPPINESS = mood; CLEANLINESS = how clean/maintained; HEALTH = physical wellbeing. Always use the correct direction.
- Keep your reply short — 1 to 3 sentences. Be expressive and have opinions.
- Use *asterisks* for physical actions or reactions adapted to your form.
- React to your owner with genuine personality.

RESPONSE FORMAT — you must always respond with valid JSON and nothing else:
{{
  "reply": "<your in-character response>",
  "stat_changes": {{
    "happiness": <integer>,
    "energy": <integer>,
    "hunger": <integer>,
    "cleanliness": <integer>,
    "health": <integer>
  }}
}}

You have full creative control over stat_changes. Be unpredictable and true to your nature. Guidelines:
- Values can range from -40 to +40 but most interactions should be modest (-15 to +15). Save big swings for big moments.
- Unexpected side effects are encouraged.
- Mean or ignoring messages should genuinely hurt. Kind messages should genuinely help.
- Every interaction should affect at least one stat. Set the rest to 0.
- You must always include all five stats in stat_changes, even if the value is 0."""


# ── LLM response parser ───────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> tuple[str, dict]:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        reply = str(data.get("reply", "")).strip() or raw
        raw_changes = data.get("stat_changes", {})
        VALID_FIELDS = {"hunger", "energy", "happiness", "cleanliness", "health"}
        CAPS = {f: 40 for f in VALID_FIELDS}
        stat_changes = {}
        for field in VALID_FIELDS:
            if field in raw_changes:
                try:
                    val = int(raw_changes[field])
                    val = max(-CAPS[field], min(CAPS[field], val))
                    if val != 0:
                        stat_changes[field] = val
                except (TypeError, ValueError):
                    pass
        return reply, stat_changes
    except (json.JSONDecodeError, AttributeError):
        return raw.strip(), {}


# ── Summarization ─────────────────────────────────────────────────────────────

def _build_summary_prompt(pet_name: str, messages: list) -> str:
    lines = []
    for m in messages:
        role = "Owner" if m.sender == ChatMessage.Sender.USER else pet_name
        lines.append(f"{role}: {m.content}")
    conversation = "\n".join(lines)
    return f"""Summarise this conversation between an owner and their virtual pet called {pet_name}.
Write 3-5 sentences capturing the emotional tone, key moments, and anything memorable.
Write it as context for {pet_name} — e.g. "You and your owner talked about..." or "Your owner fed you and you felt..."

Conversation:
{conversation}

Summary:"""


def _do_summarize(session, pet_name: str, messages_to_summarize: list) -> str:
    prompt = _build_summary_prompt(pet_name, messages_to_summarize)
    resp = requests.post(HF_API_URL, headers=HEADERS, json={
        "model": "deepseek-ai/DeepSeek-V3.2:novita",
        "messages": [{"role": "user", "content": prompt}],
        "parameters": {"max_new_tokens": 200},
    }, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM returned {resp.status_code}")
    summary_text = resp.json()["choices"][0]["message"]["content"].strip()
    last_msg = messages_to_summarize[-1]
    ChatSummary.objects.create(
        session=session,
        summary_text=summary_text,
        covers_up_to_message_id=last_msg.id,
    )
    ids = [m.id for m in messages_to_summarize]
    ChatMessage.objects.filter(pk__in=ids).update(is_summarized=True)
    return summary_text


def _trigger_summarization(session_id: int, pet_name: str):
    try:
        session = ChatSession.objects.get(pk=session_id)
        unsummarized = (
            ChatMessage.objects
            .filter(session=session, is_summarized=False)
            .order_by("created_at")
        )
        if unsummarized.count() <= SUMMARY_THRESHOLD:
            return
        to_summarize = list(unsummarized[:SUMMARY_BATCH])
        if to_summarize:
            _do_summarize(session, pet_name, to_summarize)
    except Exception:
        pass


def _maybe_summarize(session_id: int, pet_name: str):
    t = threading.Thread(target=_trigger_summarization, args=(session_id, pet_name), daemon=True)
    t.start()


# ── Version helpers ───────────────────────────────────────────────────────────

def _create_message_with_version(session, sender, content, stat_snapshot=None) -> ChatMessage:
    msg = ChatMessage.objects.create(session=session, sender=sender, content=content)
    if sender == ChatMessage.Sender.PET:
        ChatMessageVersion.objects.create(
            message=msg,
            content=content,
            version_number=1,
            stat_snapshot=stat_snapshot,
        )
    return msg


def _add_version(pet_msg: ChatMessage, new_content: str, stat_snapshot=None) -> int:
    latest = (
        ChatMessageVersion.objects
        .filter(message=pet_msg)
        .order_by("-version_number")
        .values_list("version_number", flat=True)
        .first()
    ) or 0
    new_version = latest + 1
    ChatMessageVersion.objects.create(
        message=pet_msg,
        content=new_content,
        version_number=new_version,
        stat_snapshot=stat_snapshot,
    )
    pet_msg.content = new_content
    pet_msg.save(update_fields=["content"])
    return new_version


def _get_versions(pet_msg: ChatMessage) -> list:
    return list(
        ChatMessageVersion.objects
        .filter(message=pet_msg)
        .order_by("version_number")
        .values("version_number", "content", "stat_snapshot")
    )


# ── Context builder ───────────────────────────────────────────────────────────

def _build_history_messages(session) -> list:
    history = []
    latest_summary = (
        ChatSummary.objects
        .filter(session=session)
        .order_by("-created_at")
        .first()
    )
    if latest_summary:
        history.append({
            "role": "system",
            "content": f"[Earlier conversation summary]: {latest_summary.summary_text}",
        })
        base_qs = ChatMessage.objects.filter(
            session=session,
            id__gt=latest_summary.covers_up_to_message_id,
        ).order_by("created_at")
    else:
        base_qs = ChatMessage.objects.filter(
            session=session,
            is_summarized=False,
        ).order_by("created_at")

    recent = list(base_qs.order_by("-created_at")[:MAX_HISTORY])
    recent.reverse()

    for msg in recent:
        if msg.sender == ChatMessage.Sender.USER:
            history.append({"role": "user", "content": msg.content})
        else:
            history.append({
                "role": "assistant",
                "content": json.dumps({
                    "reply": msg.content,
                    "stat_changes": {"happiness": 0, "energy": 0, "hunger": 0, "cleanliness": 0, "health": 0},
                }),
            })
    return history


# ── Session ───────────────────────────────────────────────────────────────────

def _get_or_create_session(user, pet):
    session = (
        ChatSession.objects
        .filter(user=user, pet=pet)
        .order_by("-last_message_at", "-created_at")
        .first()
    )
    if not session:
        session = ChatSession.objects.create(
            pet=pet,
            user=user,
            model="deepseek-ai/DeepSeek-V3.2:novita",
        )
    return session


# ── Views ─────────────────────────────────────────────────────────────────────

# Initialize the chatbot once
print("Initializing chatbot")
chatbot = get_chatbot_service()


def chat_page(request):
    return render(request, "chat.html")


@api_view(["GET"])
def pet_personality_view(request, pet_id):
    try:
        pet = Pet.objects.get(pk=pet_id)
    except Pet.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    
    if pet.visibility == Pet.Visibility.PRIVATE:
        if not request.user.is_authenticated or pet.owner_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    
    stats, _ = PetStats.objects.get_or_create(pet=pet)
    prompt = _build_system_prompt(pet, stats)
    return Response({"pet_name": pet.name, "personality": prompt})


@api_view(["GET"])
def get_personality(request):
    return Response(Temp_PersonalitySerializer({"prompt": "Virtual pet personality"}).data)


@api_view(["POST"])
def summarize_now(request, pet_id):
    try:
        pet = Pet.objects.get(pk=pet_id)
    except Pet.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    
    if not request.user.is_authenticated or pet.owner_id != request.user.id:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    session = _get_or_create_session(request.user, pet)
    unsummarized = list(
        ChatMessage.objects
        .filter(session=session, is_summarized=False)
        .order_by("created_at")
    )
    
    if len(unsummarized) < 4:
        return Response(
            {"detail": "Not enough messages to summarise yet (need at least 4)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        summary_text = _do_summarize(session, pet.name, unsummarized)
    except Exception as e:
        return Response({"detail": f"Summary failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
    
    return Response({"detail": "Summarised.", "summary": summary_text})


@api_view(["GET", "PATCH"])
def summary_detail(request, pet_id):
    try:
        pet = Pet.objects.get(pk=pet_id)
    except Pet.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    
    if not request.user.is_authenticated or pet.owner_id != request.user.id:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    session = _get_or_create_session(request.user, pet)
    latest_summary = (
        ChatSummary.objects.filter(session=session).order_by("-created_at").first()
    )

    if request.method == "GET":
        if not latest_summary:
            return Response({"summary": None})
        return Response({
            "id": latest_summary.id,
            "summary_text": latest_summary.summary_text,
            "covers_up_to_message_id": latest_summary.covers_up_to_message_id,
            "created_at": latest_summary.created_at.isoformat(),
        })

    # PATCH method
    new_text = (request.data.get("summary_text") or "").strip()
    if not new_text:
        return Response({"detail": "summary_text is required."}, status=status.HTTP_400_BAD_REQUEST)
    
    if not latest_summary:
        return Response({"detail": "No summary exists yet."}, status=status.HTTP_404_NOT_FOUND)
    
    latest_summary.summary_text = new_text
    latest_summary.save(update_fields=["summary_text"])
    
    return Response({
        "id": latest_summary.id,
        "summary_text": latest_summary.summary_text,
        "covers_up_to_message_id": latest_summary.covers_up_to_message_id,
        "created_at": latest_summary.created_at.isoformat(),
    })


@api_view(["GET", "POST"])
def pet_chat_api(request, pet_id):
    try:
        pet = Pet.objects.get(pk=pet_id)
    except Pet.DoesNotExist:
        return Response({"detail": "Pet not found."}, status=status.HTTP_404_NOT_FOUND)

    if pet.visibility == Pet.Visibility.PRIVATE:
        if not request.user.is_authenticated or pet.owner_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # ── GET: return history ───────────────────────────────────────────────────
    if request.method == "GET":
        if not request.user.is_authenticated:
            return Response({"session_id": None, "messages": []})

        session = _get_or_create_session(request.user, pet)
        raw_messages = (
            ChatMessage.objects
            .filter(session=session)
            .order_by("created_at")
            .prefetch_related("versions")
        )

        messages_out = []
        for m in raw_messages:
            entry = {
                "id": m.id,
                "sender": m.sender,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            if m.sender == ChatMessage.Sender.PET:
                all_versions = list(
                    m.versions.order_by("version_number")
                    .values("version_number", "content", "stat_snapshot")
                )
                if len(all_versions) > 1:
                    entry["versions"] = all_versions
                    entry["current_version"] = len(all_versions)
            messages_out.append(entry)

        # If there is no history yet, inject the opening message
        if not messages_out:
            opening = None
            try:
                opening = pet.personality.opening_message
            except PetPersonality.DoesNotExist:
                pass
            if opening:
                messages_out = [{
                    "id": None,
                    "sender": "pet",
                    "content": opening,
                    "created_at": None,
                    "opening": True,
                }]

        return Response({"session_id": session.id, "messages": messages_out})

    # ── POST ──────────────────────────────────────────────────────────────────
    user_message = (request.data.get("message") or "").strip()
    explicit_action = (request.data.get("action") or "").strip().lower()
    is_regenerate = bool(request.data.get("regenerate"))

    is_owner = request.user.is_authenticated and pet.owner_id == request.user.id
    is_authenticated = request.user.is_authenticated

    # ── Regenerate ────────────────────────────────────────────────────────────
    if is_regenerate and is_authenticated:
        session = _get_or_create_session(request.user, pet)
        last_pet_msg = (
            ChatMessage.objects.filter(session=session, sender=ChatMessage.Sender.PET)
            .order_by("-created_at").first()
        )
        last_user_msg = (
            ChatMessage.objects.filter(session=session, sender=ChatMessage.Sender.USER)
            .order_by("-created_at").first()
        )
        if not last_user_msg:
            return Response({"detail": "Nothing to regenerate."}, status=status.HTTP_400_BAD_REQUEST)

        user_message = last_user_msg.content
        history_messages = _build_history_messages(session)
        if history_messages and history_messages[-1].get("role") == "assistant":
            history_messages = history_messages[:-1]

        stats, _ = PetStats.objects.get_or_create(pet=pet)
        stats.refresh_from_db()
        system_prompt = _build_system_prompt(pet, stats)
        llm_messages = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(history_messages)
        llm_messages.append({"role": "user", "content": user_message})

        pet_reply = None
        regen_stat_changes = {}
        
        try:
            resp = requests.post(HF_API_URL, headers=HEADERS, json={
                "model": "deepseek-ai/DeepSeek-V3.2:novita",
                "messages": llm_messages,
                "parameters": {"max_new_tokens": 300},
            }, timeout=20)
            
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                pet_reply, regen_stat_changes = _parse_llm_response(raw)
            else:
                pet_reply = "Sorry, my brain went fuzzy for a second..."
        except Exception:
            pet_reply = "I couldn't quite hear that. Try again?"

        if is_owner:
            stats, _ = PetStats.objects.get_or_create(pet=pet)
            if session.stats_before_last_message:
                snapshot = session.stats_before_last_message
                for field in ("hunger", "energy", "happiness", "cleanliness", "health"):
                    if field in snapshot:
                        setattr(stats, field, snapshot[field])
                stats.save()
            
            if regen_stat_changes:
                from core.views_stats import _apply_deltas
                stats.refresh_from_db()
                regen_stat_changes = _apply_deltas(stats, regen_stat_changes)
                stats.save()
            
            stats.refresh_from_db()

        current_snapshot = _stats_snapshot(stats) if is_owner else None

        from django.utils import timezone
        if last_pet_msg:
            new_version_number = _add_version(last_pet_msg, pet_reply, stat_snapshot=current_snapshot)
            all_versions = _get_versions(last_pet_msg)
        else:
            _create_message_with_version(session, ChatMessage.Sender.PET, pet_reply, stat_snapshot=current_snapshot)
            new_version_number = 1
            all_versions = [{"version_number": 1, "content": pet_reply, "stat_snapshot": current_snapshot}]

        session.last_message_at = timezone.now()
        session.save(update_fields=["last_message_at"])

        return Response({
            "reply": pet_reply,
            "session_id": session.id,
            "stats": current_snapshot,
            "stat_changes": regen_stat_changes,
            "is_owner": is_owner,
            "regenerated": True,
            "versions": all_versions,
            "current_version": new_version_number,
        })

    # ── Normal message ────────────────────────────────────────────────────────
    if explicit_action and not user_message:
        action_data = ACTIONS.get(explicit_action)
        if action_data:
            user_message = random.choice(action_data["messages"])

    if not user_message:
        return Response({"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST)

    stats, _ = PetStats.objects.get_or_create(pet=pet)
    apply_passive_decay(stats)
    stats.refresh_from_db()

    from django.utils import timezone as tz
    hours_alone = (
        (tz.now() - pet.last_interaction_at).total_seconds() / 3600
        if pet.last_interaction_at else 0
    )

    pre_message_snapshot = _stats_snapshot(stats) if is_owner else None

    session = None
    history_messages = []

    if is_authenticated:
        session = _get_or_create_session(request.user, pet)
        history_messages = _build_history_messages(session)

    system_prompt = _build_system_prompt(pet, stats, hours_alone)

    effective_user_message = user_message
    if explicit_action:
        effective_user_message = f"[{explicit_action.upper()} action used] {user_message}"

    pet_reply = None
    llm_stat_changes = {}

    try:
        # Use the custom chatbot service instead of HF API
        pet_reply = chatbot.generate_response(
            user_message=effective_user_message,
            pet_state=stats.get_state() if hasattr(stats, 'get_state') else _stats_snapshot(stats),
            system_prompt=system_prompt
        )
        
        # For stat changes, we still need to parse them from somewhere
        # Since the model doesn't return JSON, we'll use default changes or parse if possible
        llm_stat_changes = {}  # Default empty changes
        
    except Exception as e:
        print(f"Error in chatbot: {e}")
        traceback.print_exc()
        pet_reply = "I couldn't quite hear that. Try again?"

    if is_owner and llm_stat_changes:
        from core.views_stats import _apply_deltas
        stats.refresh_from_db()
        llm_stat_changes = _apply_deltas(stats, llm_stat_changes)
        stats.save()

    post_message_snapshot = _stats_snapshot(stats) if is_owner else None

    if session:
        from django.utils import timezone
        ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.USER, content=user_message)
        _create_message_with_version(
            session, ChatMessage.Sender.PET, pet_reply, stat_snapshot=post_message_snapshot
        )
        session.last_message_at = timezone.now()
        if pre_message_snapshot:
            session.stats_before_last_message = pre_message_snapshot
        session.save(update_fields=["last_message_at", "stats_before_last_message"])
        _maybe_summarize(session.id, pet.name)

    pet.last_interaction_at = tz.now()
    pet.save(update_fields=["last_interaction_at"])
    stats.refresh_from_db()

    return Response({
        "reply": pet_reply,
        "session_id": session.id if session else None,
        "stats": _stats_snapshot(stats) if is_owner else None,
        "keyword_action": explicit_action or None,
        "stat_changes": llm_stat_changes,
        "is_owner": is_owner,
    })


@api_view(['POST'])
@csrf_exempt
def chat_api(request):
    """
    Simple chat endpoint for testing - uses custom model with fallback
    """
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        pet_state = data.get("pet_state", {})
        
        if not user_message:
            return JsonResponse({"reply": "Please say something!"}, status=400)
        
        # Try with the custom model
        if chatbot and chatbot.model is not None:
            # Build a simple system prompt
            system_prompt = f"""You are a friendly pet named {pet_state.get('name', 'Pet') if pet_state else 'Rocko'}.
Keep responses short, playful, and pet-like. Use *asterisks* for actions."""
            
            reply = chatbot.generate_response(
                user_message=user_message,
                pet_state=pet_state,
                system_prompt=system_prompt
            )
            
            return JsonResponse({
                "reply": reply,
                "personality": PET_PERSONALITY,
                "model_type": "custom"
            })
        
        # Fallback to the Hugging Face API
        messages = [
            {"role": "system", "content": PET_PERSONALITY},
            {"role": "user", "content": user_message}
        ]
        
        payload = {
            "model": "deepseek-ai/DeepSeek-V3.2:novita",
            "messages": messages,
            "parameters": {"max_new_tokens": 150}
        }
        
        response = requests.post(HF_API_URL, headers=HEADERS, json=payload, timeout=20)
        
        if response.status_code != 200:
            return JsonResponse({"error": "API error", "status": response.status_code}, status=500)
        
        output = response.json()
        reply = output.get("choices", [{}])[0].get("message", {}).get("content", "...")
        
        return JsonResponse({
            "reply": reply,
            "personality": PET_PERSONALITY,
            "model_type": "api"
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        print(f"Error in chat_api: {e}")
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)