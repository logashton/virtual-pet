import random
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pet, PetStats


# 
# Passive decay
# 

# How much each stat drops per hour of real time passing.
DECAY_RATES = {
    "hunger":      -6,   # gets hungry 
    "energy":      -4,   # gets tired  over time
    "happiness":   -3,   # gets lonely and bored if ignored
    "cleanliness": -2,   # gets dirty slowly
    # health decays separately below — only when other stats are critically low
}

# If hunger OR happiness drops below this threshold, health also decays.
HEALTH_DECAY_THRESHOLD = 20
HEALTH_DECAY_RATE = -3   # per hour while threshold is breached

# Cap how many hours of decay we apply in one go so a pet ignored for a while
# doesn't hit zero on everything the moment someone opens it
MAX_DECAY_HOURS = 24

# Cost applied to stats on each chat message sent.
CHAT_COST = {
    "energy":  -3,
    "hunger":  -2,
}


def apply_passive_decay(stats: PetStats) -> dict:
    
    #Calculate how much time has passed since stats were last saved,
    #apply proportional decay, save, and return what actually changed.
    #Safe to call multiple times — skips if less than 60 seconds have passed.
    
    now = timezone.now()
    elapsed_seconds = (now - stats.updated_at).total_seconds()

    if elapsed_seconds < 60:
        return {}

    hours = min(elapsed_seconds / 3600, MAX_DECAY_HOURS)
    changes = {}

    for field, rate_per_hour in DECAY_RATES.items():
        old = getattr(stats, field)
        new = int(round(_clamp(old + rate_per_hour * hours)))
        if new != old:
            setattr(stats, field, new)
            changes[field] = new - old

    # Health penalty if the pet is critically hungry or unhappy
    if stats.hunger <= HEALTH_DECAY_THRESHOLD or stats.happiness <= HEALTH_DECAY_THRESHOLD:
        old_health = stats.health
        new_health = int(round(_clamp(stats.health + HEALTH_DECAY_RATE * hours)))
        if new_health != old_health:
            stats.health = new_health
            changes["health"] = new_health - old_health

    if changes:
        stats.save()

    return changes


def apply_chat_cost(stats: PetStats) -> dict:
    """
    Deduct a small amount of energy and hunger for each chat message sent.
    Returns what actually changed.
    """
    changes = _apply_deltas(stats, CHAT_COST)
    if changes:
        stats.save()
    return changes



# Actions
 

ACTIONS = {
    "feed": {
        "label": "Feed",
        "messages": [
            "You carefully prepare something and offer it to your companion. You're not entirely sure what they eat, but you do your best.",
            "You find something that seems appropriate and present it. It feels like the right thing to do.",
            "You spend a while sourcing the best possible nourishment you can find and lay it out in front of your friend.",
            "You put together a small meal and place it nearby, hoping it hits the spot.",
        ],
    },
    "play": {
        "label": "Play",
        "messages": [
            "You spend a long time playing with your companion, making up games as you go. Neither of you wants to stop.",
            "You invent an activity perfectly suited to whatever your friend is, and throw yourself into it completely.",
            "You clear some space and dedicate the next while entirely to having fun together.",
            "You engage your companion in an enthusiastic play session, whatever that looks like for something like them.",
        ],
    },
    "clean": {
        "label": "Clean",
        "messages": [
            "You spend a long time carefully scrubbing your companion until they're absolutely gleaming.",
            "You gather your best cleaning supplies and get to work, making sure every surface is spotless.",
            "You dedicate a solid chunk of time to thorough grooming, taking real pride in the result.",
            "You carefully clean every part of your companion, making sure nothing is missed.",
        ],
    },
    "rest": {
        "label": "Rest",
        "messages": [
            "You find a quiet spot and settle your companion in for a long, undisturbed rest.",
            "You make sure everything is calm and comfortable, then leave your friend to recharge in peace.",
            "You dim the lights, clear the noise, and give your companion the rest they deserve.",
            "You tuck your companion in and sit quietly nearby while they rest.",
        ],
    },
}

KEYWORD_MAP = {
    "feed": "feed", "food": "feed", "eat": "feed", "hungry": "feed",
    "snack": "feed", "dinner": "feed", "lunch": "feed", "breakfast": "feed",
    "play": "play", "fetch": "play", "game": "play", "fun": "play", "trick": "play",
    "clean": "clean", "bath": "clean", "wash": "clean", "groom": "clean", "shower": "clean",
    "rest": "rest", "sleep": "rest", "nap": "rest", "tired": "rest", "bed": "rest",
}



# Helpers------
 

def _clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def _apply_deltas(stats, deltas):
    """Apply stat deltas in-place, clamping to valid range. Returns dict of actual changes."""
    changes = {}
    for field, delta in deltas.items():
        old = getattr(stats, field)
        new = _clamp(old + delta)
        setattr(stats, field, new)
        if new != old:
            changes[field] = new - old
    return changes


def detect_keyword_action(message: str):
    """Return an action key if the message contains a known keyword, else None."""
    words = message.lower().split()
    for word in words:
        clean = word.strip(".,!?;:'\"")
        if clean in KEYWORD_MAP:
            return KEYWORD_MAP[clean]
    return None


def perform_action(pet, action_key):
    """
    Returns a random narrative message for the given action.
    Stat changes are handled entirely by the LLM.
    """
    action = ACTIONS.get(action_key)
    if not action:
        return None
    return random.choice(action["messages"])


def _stats_snapshot(stats):
    return {
        "hunger":      stats.hunger,
        "energy":      stats.energy,
        "happiness":   stats.happiness,
        "cleanliness": stats.cleanliness,
        "health":      stats.health,
        "level":       stats.level,
        "experience":  stats.experience,
    }



# Views


class PetStatsView(APIView):
    def get(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if pet.visibility == Pet.Visibility.PRIVATE:
            if not request.user.is_authenticated or pet.owner_id != request.user.id:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        stats, _ = PetStats.objects.get_or_create(pet=pet)
        apply_passive_decay(stats)          # apply decay before returning
        stats.refresh_from_db()
        return Response(_stats_snapshot(stats))


class PetActionView(APIView):
    def post(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if pet.visibility == Pet.Visibility.PRIVATE:
            if not request.user.is_authenticated or pet.owner_id != request.user.id:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        action_key = (request.data.get("action") or "").strip().lower()
        if action_key not in ACTIONS:
            return Response(
                {"detail": f"Unknown action. Valid: {list(ACTIONS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_owner = request.user.is_authenticated and pet.owner_id == request.user.id

        # Apply decay before the action so stats are up to date
        if is_owner:
            stats, _ = PetStats.objects.get_or_create(pet=pet)
            apply_passive_decay(stats)
            stats.refresh_from_db()

        reaction, snapshot, changes = perform_action(pet, action_key, is_owner)

        return Response({
            "reaction": reaction,
            "stats": snapshot,
            "changes": changes,
            "is_owner": is_owner,
        })