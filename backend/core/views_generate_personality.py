import base64
import io
import json
import os
import re

import requests
from PIL import Image
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

VALID_TONES = [
    "neutral", "snarky", "gentle", "dramatic", "anxious",
    "stoic", "cheerful", "sad", "aggressive", "mysterious",
]

VALID_TRAITS = [
    "curious", "lazy", "loyal", "mischievous", "wise",
    "cowardly", "brave", "jealous", "affectionate", "aloof",
    "greedy", "generous", "paranoid", "optimistic", "pessimistic",
]

PERSONALITY_PROMPT = f"""Look at this image and generate a personality profile for a virtual pet. Be genuinely creative and unexpected — do not default to cute or wholesome. The best results are weird, specific, and fully committed.

The pet could be literally anything. A mundane object with an existential crisis. A food item with strong opinions about being eaten. A household appliance with deeply held grudges. Whatever it is, commit to it completely — the more specific and strange, the better.

Also generate custom stat reaction text for each stat. Write 1 sentence in second person that reflects exactly how THIS specific thing experiences that state. A stapler running out of staples is not the same as a dog being hungry. Make it count.

Stats:
- HUNGER = satiation (high = full/satisfied, low = starving)
- ENERGY = alertness (high = energised, low = exhausted)
- HAPPINESS = mood
- CLEANLINESS = how clean/maintained
- HEALTH = physical wellbeing

Return ONLY valid JSON, no extra text, no markdown fences:
{{
  "self_concept": "<what this thing actually is — be specific and strange>",
  "tone": "<one of: neutral, snarky, gentle, dramatic, anxious, stoic, cheerful, sad, aggressive, mysterious>",
  "traits": ["<trait1>", "<trait2>", "<trait3>"],
  "stat_reactions": {{
    "hunger": {{
      "critical": "<1 sentence: extreme deprivation for this thing>",
      "low": "<1 sentence: mild need>",
      "high": "<1 sentence: fully satisfied>"
    }},
    "energy": {{
      "critical": "<1 sentence: complete exhaustion>",
      "low": "<1 sentence: low energy>",
      "high": "<1 sentence: fully energised>"
    }},
    "happiness": {{
      "critical": "<1 sentence: deep unhappiness specific to this thing>",
      "low": "<1 sentence: mild gloom>",
      "high": "<1 sentence: thriving>"
    }},
    "cleanliness": {{
      "critical": "<1 sentence: very dirty/neglected>",
      "low": "<1 sentence: slightly unkempt>"
    }},
    "health": {{
      "critical": "<1 sentence: very unwell/damaged>",
      "low": "<1 sentence: below-average health>"
    }}
  }}
}}

Rules:
- tone must be EXACTLY one of: {", ".join(VALID_TONES)}
- traits must be 2-4 items chosen ONLY from: {", ".join(VALID_TRAITS)}
- Every field should feel written specifically for THIS thing, not a generic pet"""


APPEARANCE_PROMPT = f"""Look at this image. Describe this thing as if it were a virtual pet — but do it with genuine creative commitment. Avoid the obvious. Avoid cute. Find the weird angle.

Also generate custom stat reactions and an opening message that fit this specific thing's nature.

Stats:
- HUNGER = satiation (high = full/satisfied, low = starving)
- ENERGY = alertness (high = energised, low = exhausted)
- HAPPINESS = mood
- CLEANLINESS = how clean/maintained
- HEALTH = physical wellbeing

Return ONLY valid JSON, no extra text, no markdown fences:
{{
  "appearance": "<physical description — 1-2 sentences, find what makes it interesting>",
  "backstory": "<backstory that commits to the bit>",
  "quirks": "<specific habits that only make sense for this exact thing>",
  "likes": "<things they like, specific and in-character>",
  "dislikes": "<things they dislike>",
  "opening_message": "<the first thing this thing says when chat opens — drop the owner straight into the character, 1-3 sentences>",
  "stat_reactions": {{
    "hunger": {{
      "critical": "<1 sentence: extreme deprivation for this thing>",
      "low": "<1 sentence: mild need>",
      "high": "<1 sentence: fully satisfied>"
    }},
    "energy": {{
      "critical": "<1 sentence: complete exhaustion>",
      "low": "<1 sentence: low energy>",
      "high": "<1 sentence: fully energised>"
    }},
    "happiness": {{
      "critical": "<1 sentence: deep unhappiness specific to this thing>",
      "low": "<1 sentence: mild gloom>",
      "high": "<1 sentence: thriving>"
    }},
    "cleanliness": {{
      "critical": "<1 sentence: very dirty/neglected>",
      "low": "<1 sentence: slightly unkempt>"
    }},
    "health": {{
      "critical": "<1 sentence: very unwell/damaged>",
      "low": "<1 sentence: below-average health>"
    }}
  }}
}}

Every field should feel written specifically for THIS thing. The opening_message should not be a greeting — it should establish character immediately."""

OPENING_MESSAGE_PROMPT = """Given this pet's personality, write an opening message — the first thing they say when the owner opens a fresh chat.

Pet details:
{details}

Rules:
- 1-3 sentences total
- Drop straight into character — no generic greetings
- You can include a brief *italicised* scene-setting line before the dialogue if it adds atmosphere
- Make it immediately memorable and specific to this character
- It should feel like walking in on something already happening

Return ONLY the opening message text, nothing else."""


def _image_to_base64(image_bytes: bytes) -> tuple[str, str]:
    """Convert raw image bytes to base64 string and return (b64_string, mime_type)."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, "image/jpeg"


def _call_openrouter_vision(image_b64: str, media_type: str, prompt: str) -> dict:
    """
    Call openrouter model  via OpenRouter and return parsed JSON dict.
    Reads OPENROUTER_API_KEY from the environment.
    """
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "xiaomi/mimo-v2.5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                    ],
                }
            ],
        }),
        timeout=30,
    )
    print("OpenRouter status:", response.status_code)
    #print("OpenRouter response:", response.text)  
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    return json.loads(raw)


def _call_openrouter_text(prompt: str) -> str:
    """Call OpenRouter with a text-only prompt and return the raw response string."""
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "xiaomi/mimo-v2.5",
            "messages": [{"role": "user", "content": prompt}],
        }),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _safe_str(val) -> str:
    """Coerce a value to a clean string, handling lists returned by some models."""
    if isinstance(val, list):
        return ', '.join(str(v) for v in val).strip()
    return (val or '').strip()


def _sanitise_stat_reactions(raw: dict) -> dict:
    """Ensure stat_reactions has the expected structure, filling gaps with empty strings."""
    STATS = {
        "hunger":      ["critical", "low", "high"],
        "energy":      ["critical", "low", "high"],
        "happiness":   ["critical", "low", "high"],
        "cleanliness": ["critical", "low"],
        "health":      ["critical", "low"],
    }
    result = {}
    for stat, buckets in STATS.items():
        result[stat] = {}
        stat_data = raw.get(stat, {}) if isinstance(raw, dict) else {}
        for bucket in buckets:
            result[stat][bucket] = _safe_str(stat_data.get(bucket))
    return result


def _sanitise_personality(data: dict) -> dict:
    tone = _safe_str(data.get("tone")).lower()
    if tone not in VALID_TONES:
        tone = "neutral"

    raw_traits = data.get("traits") or []
    if isinstance(raw_traits, str):
        raw_traits = [t.strip() for t in raw_traits.split(",")]
    traits = [t.strip().lower() for t in raw_traits if t.strip().lower() in VALID_TRAITS][:4]

    return {
        "self_concept":   _safe_str(data.get("self_concept")),
        "tone":           tone,
        "traits":         traits,
        "stat_reactions": _sanitise_stat_reactions(data.get("stat_reactions") or {}),
    }


def _sanitise_appearance(data: dict) -> dict:
    return {
        "appearance":      _safe_str(data.get("appearance")),
        "backstory":       _safe_str(data.get("backstory")),
        "quirks":          _safe_str(data.get("quirks")),
        "likes":           _safe_str(data.get("likes")),
        "dislikes":        _safe_str(data.get("dislikes")),
        "opening_message": _safe_str(data.get("opening_message")),
        "stat_reactions":  _sanitise_stat_reactions(data.get("stat_reactions") or {}),
    }


class GeneratePersonalityView(APIView):
    """
    POST /api/generate-personality/

    Body: multipart/form-data
      image  — the uploaded photo (required for mode=personality/appearance)
      mode   — "personality" (default), "appearance", or "opening"

    For mode="opening", image is optional. Instead pass:
      pet_name      — name of the pet
      self_concept  — what the pet is
      tone          — tone
      traits        — comma-separated traits
      backstory     — backstory

    Returns JSON with suggested fields.
    Requires authentication.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        mode = (request.data.get("mode") or "personality").strip().lower()

        # Opening message generation — text only, no image required
        if mode == "opening":
            pet_name     = (request.data.get("pet_name") or "").strip()
            self_concept = (request.data.get("self_concept") or "").strip()
            tone         = (request.data.get("tone") or "").strip()
            traits       = (request.data.get("traits") or "").strip()
            backstory    = (request.data.get("backstory") or "").strip()

            details_lines = []
            if pet_name:     details_lines.append(f"Name: {pet_name}")
            if self_concept: details_lines.append(f"Identity: {self_concept}")
            if tone:         details_lines.append(f"Tone: {tone}")
            if traits:       details_lines.append(f"Traits: {traits}")
            if backstory:    details_lines.append(f"Backstory: {backstory}")

            if not details_lines:
                return Response(
                    {"detail": "Provide at least one of: pet_name, self_concept, tone, traits, backstory."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            prompt = OPENING_MESSAGE_PROMPT.format(details="\n".join(details_lines))
            try:
                opening_message = _call_openrouter_text(prompt)
            except Exception as e:
                return Response(
                    {"detail": f"Generation failed: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response({"opening_message": opening_message.strip()})

        # Vision modes — require image
        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"detail": "Missing 'image' file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw = image_file.read()
        except Exception:
            return Response({"detail": "Could not read image."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            Image.open(io.BytesIO(raw)).verify()
        except Exception:
            return Response({"detail": "Invalid or unsupported image."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            image_b64, media_type = _image_to_base64(raw)
        except Exception:
            return Response({"detail": "Could not process image."}, status=status.HTTP_400_BAD_REQUEST)

        prompt = PERSONALITY_PROMPT if mode == "personality" else APPEARANCE_PROMPT

        try:
            raw_data = _call_openrouter_vision(image_b64, media_type, prompt)
        except json.JSONDecodeError:
            return Response(
                {"detail": "AI returned invalid JSON. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {"detail": f"Generation failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if mode == "personality":
            result = _sanitise_personality(raw_data)
        else:
            result = _sanitise_appearance(raw_data)

        return Response(result, status=status.HTTP_200_OK)