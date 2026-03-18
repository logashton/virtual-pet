from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pet, PetPersonality


VALID_TONES = [
    "neutral", "snarky", "gentle", "dramatic", "anxious",
    "stoic", "cheerful", "sad", "aggressive", "mysterious",
]

VALID_TRAITS = [
    "curious", "lazy", "loyal", "mischievous", "wise",
    "cowardly", "brave", "jealous", "affectionate", "aloof",
    "greedy", "generous", "paranoid", "optimistic", "pessimistic",
]

STAT_KEYS = ["hunger", "energy", "happiness", "cleanliness", "health"]

STAT_THRESHOLDS = {
    "hunger":      {"critical": 15, "low": 35, "high": 85},
    "energy":      {"critical": 15, "low": 35, "high": 85},
    "happiness":   {"critical": 15, "low": 35, "high": 85},
    "cleanliness": {"critical": 20, "low": 40, "high": None},
    "health":      {"critical": 30, "low": 50, "high": None},
}

DEFAULT_REACTIONS = {
    "hunger": {
        "critical": "Your HUNGER stat is critically low. Whatever hunger means for something like you, you are at the extreme of it and it is consuming your thoughts.",
        "low":      "Your HUNGER stat is low. You feel a strong craving or need — interpret what that means for what you are.",
        "high":     "Your HUNGER stat is very high. You feel completely satisfied and fulfilled in whatever way makes sense for you.",
    },
    "energy": {
        "critical": "Your ENERGY stat is critically low. You are barely functioning. Your responses are slow and effortful.",
        "low":      "Your ENERGY stat is low. You feel sluggish and depleted.",
        "high":     "Your ENERGY stat is very high. You are buzzing and operating at full capacity.",
    },
    "happiness": {
        "critical": "Your HAPPINESS stat is critically low. You are in a deep funk and not okay. You make this known.",
        "low":      "Your HAPPINESS stat is low. You are glum and deflated.",
        "high":     "Your HAPPINESS stat is very high. You are absolutely thriving and delighted.",
    },
    "cleanliness": {
        "critical": "Your CLEANLINESS stat is critically low. You feel grimy or neglected in whatever way applies to you. You bring this up.",
        "low":      "Your CLEANLINESS stat is low. You could do with some attention.",
        "high":     "",
    },
    "health": {
        "critical": "Your HEALTH stat is very low. Something feels fundamentally wrong. You mention feeling off.",
        "low":      "Your HEALTH stat is below average. You are not at your best.",
        "high":     "",
    },
}


def get_stat_reactions(personality=None):
    """
    Return the effective stat reactions dict, merging saved custom reactions
    over the defaults. Falls back gracefully if no personality is set.
    """
    result = {}
    for stat, buckets in DEFAULT_REACTIONS.items():
        result[stat] = dict(buckets)

    if personality is None:
        return result

    try:
        saved = personality.stat_reactions
    except AttributeError:
        return result

    if not isinstance(saved, dict):
        return result

    for stat in STAT_KEYS:
        if stat in saved and isinstance(saved[stat], dict):
            for bucket in ("critical", "low", "high"):
                val = saved[stat].get(bucket)
                if val:
                    result[stat][bucket] = val

    return result


class PetPersonalityView(APIView):
    """
    GET    /api/pets/<id>/personality/  — retrieve personality
    PATCH  /api/pets/<id>/personality/  — create or update personality fields
    DELETE /api/pets/<id>/personality/  — reset to default
    """

    def _get_pet_or_403(self, pk, user):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not user.is_authenticated or pet.owner_id != user.id:
            return None, Response(
                {"detail": "Only the owner can manage this pet's personality."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return pet, None

    def get(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if pet.visibility == Pet.Visibility.PRIVATE:
            if not request.user.is_authenticated or pet.owner_id != request.user.id:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return Response(_serialize(pet.personality))
        except PetPersonality.DoesNotExist:
            return Response(_empty())

    def patch(self, request, pk):
        pet, err = self._get_pet_or_403(pk, request.user)
        if err:
            return err

        data = request.data
        errors = {}

        if "tone" in data:
            tone_val = (data["tone"] or "").strip().lower()
            if tone_val and tone_val not in VALID_TONES:
                errors["tone"] = f"Must be one of: {', '.join(VALID_TONES)}"

        if "traits" in data:
            raw = data["traits"]
            if not isinstance(raw, list):
                errors["traits"] = "Must be a JSON array of trait strings."

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            p = pet.personality
        except PetPersonality.DoesNotExist:
            p = PetPersonality(pet=pet, roleplay_prompt="", traits={})

        if "self_concept" in data:
            t = _traits_dict(p)
            t["self_concept"] = (data["self_concept"] or "").strip()
            p.traits = t
        if "traits" in data:
            t = _traits_dict(p)
            t["list"] = data["traits"]
            p.traits = t
        if "tone" in data:
            p.tone = (data["tone"] or "").strip().lower() or None
        if "roleplay_prompt" in data:
            p.roleplay_prompt = (data["roleplay_prompt"] or "").strip()
        if "opening_message" in data:
            p.opening_message = (data["opening_message"] or "").strip() or None
        if "stat_reactions" in data:
            try:
                p.stat_reactions = data["stat_reactions"] if isinstance(data["stat_reactions"], dict) else {}
            except AttributeError:
                pass

        p.save()
        return Response(_serialize(p))

    def delete(self, request, pk):
        pet, err = self._get_pet_or_403(pk, request.user)
        if err:
            return err
        try:
            pet.personality.delete()
        except PetPersonality.DoesNotExist:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


def _traits_dict(p):
    if isinstance(p.traits, dict):
        return dict(p.traits)
    return {"list": p.traits or [], "self_concept": ""}


def _serialize(p):
    td = _traits_dict(p)
    return {
        "self_concept":      td.get("self_concept", ""),
        "traits":            td.get("list", []),
        "tone":              p.tone or "",
        "roleplay_prompt":   p.roleplay_prompt or "",
        "opening_message":   p.opening_message or "",
        "stat_reactions":    p.stat_reactions if isinstance(p.stat_reactions, dict) else {},
        "default_reactions": DEFAULT_REACTIONS,
        "stat_thresholds":   STAT_THRESHOLDS,
        "updated_at":        p.updated_at.isoformat(),
        "valid_tones":       VALID_TONES,
        "valid_traits":      VALID_TRAITS,
    }


def _empty():
    return {
        "self_concept":      "",
        "traits":            [],
        "tone":              "",
        "roleplay_prompt":   "",
        "opening_message":   "",
        "stat_reactions":    {},
        "default_reactions": DEFAULT_REACTIONS,
        "stat_thresholds":   STAT_THRESHOLDS,
        "updated_at":        None,
        "valid_tones":       VALID_TONES,
        "valid_traits":      VALID_TRAITS,
    }