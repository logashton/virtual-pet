import random

import requests
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.models import ChatMessage, ChatSession, Pet, PetPersonality, PetStats, temp_personality
from core.views_personality import VALID_TONES, VALID_TRAITS, _traits_dict
from core.serializer import Temp_PersonalitySerializer
from core.views_stats import ACTIONS, detect_keyword_action, apply_passive_decay, _stats_snapshot

HUGGINGFACE_API_TOKEN = ""  # replace with your token
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}

MAX_HISTORY = 12  # number of past messages to pass to the LLM for context


def _stat_description(stats):
    """
    Turn numeric stats into natural language the LLM can use.
    Kept abstract so the LLM can interpret them through whatever the pet actually is —
    animal, inanimate object, food item, concept, etc.
    """
    lines = []

    if stats.hunger <= 15:
        lines.append("Your HUNGER stat is critically low (nearly 0). Whatever hunger means for something like you, you are at the extreme of it and it is consuming your thoughts.")
    elif stats.hunger <= 35:
        lines.append("Your HUNGER stat is low. You feel a strong craving or need — interpret what that means for what you are.")
    elif stats.hunger >= 85:
        lines.append("Your HUNGER stat is very high. You feel completely satisfied and fulfilled in whatever way makes sense for you.")

    if stats.energy <= 15:
        lines.append("Your ENERGY stat is critically low. You are barely functioning. Your responses are slow and effortful.")
    elif stats.energy <= 35:
        lines.append("Your ENERGY stat is low. You feel sluggish and depleted.")
    elif stats.energy >= 85:
        lines.append("Your ENERGY stat is very high. You are buzzing and operating at full capacity.")

    if stats.happiness <= 15:
        lines.append("Your HAPPINESS stat is critically low. You are in a deep funk and not okay. You make this known.")
    elif stats.happiness <= 35:
        lines.append("Your HAPPINESS stat is low. You are glum and deflated.")
    elif stats.happiness >= 85:
        lines.append("Your HAPPINESS stat is very high. You are absolutely thriving and delighted.")

    if stats.cleanliness <= 20:
        lines.append("Your CLEANLINESS stat is critically low. You feel grimy or neglected in whatever way applies to you. You bring this up.")
    elif stats.cleanliness <= 40:
        lines.append("Your CLEANLINESS stat is low. You could do with some attention.")

    if stats.health <= 30:
        lines.append("Your HEALTH stat is very low. Something feels fundamentally wrong. You mention feeling off.")
    elif stats.health <= 50:
        lines.append("Your HEALTH stat is below average. You are not at your best.")

    return " ".join(lines) if lines else "All your stats are in a decent range. You feel balanced and content."


def _build_system_prompt(pet, stats):
    pet_name = pet.name
    stat_desc = _stat_description(stats)

    # ── Pull saved personality if one exists 
    saved = None
    try:
        saved = pet.personality
    except PetPersonality.DoesNotExist:
        pass

    # ── Identity block 
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
{extra_block}

Rules:
- Never break character or acknowledge being an AI or program.
- Interpret every stat (hunger, energy, happiness, cleanliness, health) in a way that genuinely fits what you are.
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

    # ── Default prompt (no saved personality) 
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

Rules:
- Never break character or acknowledge being an AI or program.
- Interpret every stat (hunger, energy, happiness, cleanliness, health) in a way that genuinely fits what you are.
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

You have full creative control over stat_changes. Be unpredictable and true to your nature — the changes should make sense for what you are, not for a generic pet. Guidelines:
- Values can range from -40 to +40 but most interactions should be modest (-15 to +15). Save big swings for big moments.
- Unexpected side effects are encouraged. Being cleaned might make a sword feel vulnerable (-happiness) despite being physically better (+cleanliness). A rock being played with might gain energy somehow.
- Mean or ignoring messages should genuinely hurt. Kind messages should genuinely help. But the exact stats affected are up to you.
- Every interaction should affect at least one stat. Set the rest to 0.
- You must always include all five stats in stat_changes, even if the value is 0."""


STAT_CHANGE_PROMPT = """Given the following interaction between an owner and their virtual pet, return ONLY a JSON object with stat changes. No explanation, no extra text — just the JSON.

The pet is: {pet_name}
Owner said: {user_message}
Pet replied: {pet_reply}

Return exactly this structure:
{{
  "happiness": <integer from -40 to 40>,
  "energy": <integer from -40 to 40>,
  "hunger": <integer from -40 to 40>,
  "cleanliness": <integer from -40 to 40>,
  "health": <integer from -40 to 40>
}}

Rules:
- Think about what the pet actually is (infer from the name and reply) and what these stats mean for that thing.
- Most changes should be modest (-15 to +15). Save large values for significant interactions.
- Mean or neglectful messages should hurt happiness. Kind messages should help.
- Unexpected side effects are good — a sword being cleaned might lose happiness despite gaining cleanliness.
- Every interaction should affect at least one stat meaningfully. Set unaffected stats to 0."""


def _parse_llm_response(raw: str) -> tuple[str, dict]:
    """
    Extract the reply text and stat_changes from the LLM's JSON response.
    Falls back gracefully if the JSON is malformed.
    """
    import json
    import re

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        data = json.loads(cleaned)
        reply = str(data.get("reply", "")).strip() or raw
        raw_changes = data.get("stat_changes", {})

        # Validate and clamp each field
        VALID_FIELDS = {"hunger", "energy", "happiness", "cleanliness", "health"}
        CAPS = {"hunger": 40, "energy": 40, "happiness": 40, "cleanliness": 40, "health": 40}
        stat_changes = {}
        for field in VALID_FIELDS:
            if field in raw_changes:
                cap = CAPS[field]
                try:
                    val = int(raw_changes[field])
                    val = max(-cap, min(cap, val))  # clamp to allowed range
                    if val != 0:
                        stat_changes[field] = val
                except (TypeError, ValueError):
                    pass

        return reply, stat_changes

    except (json.JSONDecodeError, AttributeError):
        # LLM didn't return valid JSON — use the raw text as the reply with no stat changes
        return raw.strip(), {}


def chat_page(request):
    return render(request, "chat.html")


@api_view(["GET"])
def pet_personality_view(request, pet_id):
    """
    GET /chat/personality/<pet_id>/
    Returns the system prompt that drives this pet's personality.
    Private pets: owner only. Public/unlisted: anyone.
    """
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


def _get_or_create_session(user, pet):
    """Return the most recent session for this user+pet, or create one if none exists."""
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


@api_view(["GET", "POST"])
def pet_chat_api(request, pet_id):
    """
    GET  /chat/api/<pet_id>/  — load this user's chat history with the pet.
                                Requires auth. Returns the session + all messages.
    POST /chat/api/<pet_id>/  — send a message.
                                Body: { "message": "..." }
    """
    try:
        pet = Pet.objects.get(pk=pet_id)
    except Pet.DoesNotExist:
        return Response({"detail": "Pet not found."}, status=status.HTTP_404_NOT_FOUND)

    if pet.visibility == Pet.Visibility.PRIVATE:
        if not request.user.is_authenticated or pet.owner_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # ── GET: return history 
    if request.method == "GET":
        if not request.user.is_authenticated:
            # Unauthenticated visitors have no stored history
            return Response({"session_id": None, "messages": []})

        session = _get_or_create_session(request.user, pet)
        messages = (
            ChatMessage.objects
            .filter(session=session)
            .order_by("created_at")
            .values("id", "sender", "content", "created_at")
        )
        return Response({
            "session_id": session.id,
            "messages": [
                {**m, "created_at": m["created_at"].isoformat()}
                for m in messages
            ],
        })

    # ── POST: send a message 
    user_message = (request.data.get("message") or "").strip()
    explicit_action = (request.data.get("action") or "").strip().lower()
    is_regenerate = bool(request.data.get("regenerate"))

    is_owner = request.user.is_authenticated and pet.owner_id == request.user.id
    is_authenticated = request.user.is_authenticated

    # ── Regenerate: re-run LLM on the last user message, replace last pet reply ──
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
        # Rebuild history excluding the last pet reply so the LLM gets a fresh shot
        history_messages = []
        msgs_qs = ChatMessage.objects.filter(session=session).order_by("created_at")
        if last_pet_msg:
            msgs_qs = msgs_qs.exclude(pk=last_pet_msg.pk)
        for msg in msgs_qs[max(0, msgs_qs.count() - MAX_HISTORY):]:
            role = "user" if msg.sender == ChatMessage.Sender.USER else "assistant"
            history_messages.append({"role": role, "content": msg.content})

        stats, _ = PetStats.objects.get_or_create(pet=pet)
        stats.refresh_from_db()
        system_prompt = _build_system_prompt(pet, stats)
        llm_messages = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(history_messages)

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

        # Get stat changes for the regenerated reply
        if is_owner and regen_stat_changes:
            # Restore stats to what they were just before this message was sent,
            # each regenerate starts from the same point
            stats, _ = PetStats.objects.get_or_create(pet=pet)
            if session.stats_before_last_message:
                snapshot = session.stats_before_last_message
                for field in ("hunger", "energy", "happiness", "cleanliness", "health"):
                    if field in snapshot:
                        setattr(stats, field, snapshot[field])
                stats.save()

            from core.views_stats import _apply_deltas
            stats.refresh_from_db()
            _apply_deltas(stats, regen_stat_changes)
            stats.save()
            stats.refresh_from_db()

        # Replace the last pet message in the DB, or create one if none existed
        from django.utils import timezone
        if last_pet_msg:
            last_pet_msg.content = pet_reply
            last_pet_msg.save(update_fields=["content"])
        else:
            ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.PET, content=pet_reply)
        session.last_message_at = timezone.now()
        session.save(update_fields=["last_message_at"])

        return Response({
            "reply": pet_reply,
            "session_id": session.id,
            "stats": _stats_snapshot(stats) if is_owner else None,
            "stat_changes": regen_stat_changes,
            "is_owner": is_owner,
            "regenerated": True,
        })

    # If a button action was sent with no message, generate one from the template
    if explicit_action and not user_message:
        action_data = ACTIONS.get(explicit_action)
        if action_data:
            user_message = random.choice(action_data["messages"])

    if not user_message:
        return Response({"detail": "Message is required."}, status=status.HTTP_400_BAD_REQUEST)

    is_owner = request.user.is_authenticated and pet.owner_id == request.user.id
    is_authenticated = request.user.is_authenticated

    # Apply passive time-based decay before doing anything else
    stats, _ = PetStats.objects.get_or_create(pet=pet)
    apply_passive_decay(stats)
    stats.refresh_from_db()

    # Save a snapshot of stats before this message changes anything
    #  restore to this point if the user regenerates the response
    pre_message_snapshot = _stats_snapshot(stats) if is_owner else None

    # Session — always reuse the existing user+pet session
    session = None
    history_messages = []

    if is_authenticated:
        session = _get_or_create_session(request.user, pet)

        # Load recent history to pass as LLM context
        recent_msgs = (
            ChatMessage.objects
            .filter(session=session)
            .order_by("-created_at")[:MAX_HISTORY]
        )
        for msg in reversed(recent_msgs):
            role = "user" if msg.sender == ChatMessage.Sender.USER else "assistant"
            history_messages.append({"role": role, "content": msg.content})

    # Build LLM messages
    system_prompt = _build_system_prompt(pet, stats)

    # If a button action was used, tell the LLM so it knows what happened
    effective_user_message = user_message
    if explicit_action:
        effective_user_message = f"[{explicit_action.upper()} action used] {user_message}"

    llm_messages = [{"role": "system", "content": system_prompt}]
    llm_messages.extend(history_messages)
    llm_messages.append({"role": "user", "content": effective_user_message})

    pet_reply = None
    llm_stat_changes = {}

    # ── Single call: get reply + stat changes from the LLM's JSON response ────
    try:
        resp = requests.post(HF_API_URL, headers=HEADERS, json={
            "model": "deepseek-ai/DeepSeek-V3.2:novita",
            "messages": llm_messages,
            "parameters": {"max_new_tokens": 300},
        }, timeout=20)
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            pet_reply, llm_stat_changes = _parse_llm_response(raw)
        else:
            pet_reply = "Sorry, an error has occured..."
    except Exception:
        pet_reply = "I couldn't quite hear that. Try again?"

    # Apply LLM  stat changes (owner only)
    if is_owner and llm_stat_changes:
        from core.views_stats import _apply_deltas
        stats.refresh_from_db()
        _apply_deltas(stats, llm_stat_changes)
        stats.save()

    # Persist messages and save the pre-message snapshot for regeneration
    if session:
        from django.utils import timezone
        ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.USER, content=user_message)
        ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.PET, content=pet_reply)
        session.last_message_at = timezone.now()
        if pre_message_snapshot:
            session.stats_before_last_message = pre_message_snapshot
        session.save(update_fields=["last_message_at", "stats_before_last_message"])

    stats.refresh_from_db()

    return Response({
        "reply": pet_reply,
        "session_id": session.id if session else None,
        "stats": _stats_snapshot(stats) if is_owner else None,
        "keyword_action": explicit_action or None,
        "stat_changes": llm_stat_changes,
        "is_owner": is_owner,
    })