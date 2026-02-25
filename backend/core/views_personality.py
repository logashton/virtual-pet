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


class PetPersonalityView(APIView):
    """
    GET    /api/pets/<id>/personality/  — retrieve personality (owner only)
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
        # Private pets: owner only. Public/unlisted: anyone can view personality.
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
        "self_concept":    td.get("self_concept", ""),
        "traits":          td.get("list", []),
        "tone":            p.tone or "",
        "roleplay_prompt": p.roleplay_prompt or "",
        "updated_at":      p.updated_at.isoformat(),
        "valid_tones":     VALID_TONES,
        "valid_traits":    VALID_TRAITS,
    }


def _empty():
    return {
        "self_concept":    "",
        "traits":          [],
        "tone":            "",
        "roleplay_prompt": "",
        "updated_at":      None,
        "valid_tones":     VALID_TONES,
        "valid_traits":    VALID_TRAITS,
    }
