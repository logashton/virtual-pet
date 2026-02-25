from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .models import ModerationReport, Pet, User

PET_TRAIT_OPTIONS = [
    "curious",
    "lazy",
    "loyal",
    "mischievous",
    "wise",
    "cowardly",
    "brave",
    "jealous",
    "affectionate",
    "aloof",
    "greedy",
    "generous",
    "paranoid",
    "optimistic",
    "pessimistic",
]
DISCOVER_TAG_OPTIONS = PET_TRAIT_OPTIONS[:7]


def _pet_card_data(pet: Pet):
    image_url = None
    for asset in pet.assets.all():
        if asset.cutout_image_url or asset.original_image_url:
            image_url = asset.cutout_image_url or asset.original_image_url
            break

    description = ""
    traits = []
    try:
        personality = pet.personality
        roleplay_prompt = (personality.roleplay_prompt or "").strip()
        for line in roleplay_prompt.splitlines():
            line = line.strip()
            if line.lower().startswith("backstory:"):
                description = line.split(":", 1)[1].strip()
                break
        raw_traits = personality.traits
        if isinstance(raw_traits, dict):
            raw_traits = raw_traits.get("list", [])
        if isinstance(raw_traits, list):
            traits = [str(t).strip() for t in raw_traits if str(t).strip()][:5]
    except Exception:
        pass

    if not description:
        description = "No description yet."

    return {
        "id": pet.id,
        "name": pet.name,
        "owner_name": pet.owner.display_name or pet.owner.username,
        "description": description,
        "traits": traits,
        "image_url": image_url,
    }


def _pet_matches_search(pet: Pet, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True

    if q in (pet.name or "").lower():
        return True

    try:
        personality = pet.personality
    except Exception:
        return False

    if q in (personality.roleplay_prompt or "").lower():
        return True

    raw_traits = personality.traits
    if isinstance(raw_traits, dict):
        raw_traits = raw_traits.get("list", [])
    if isinstance(raw_traits, list):
        for t in raw_traits:
            if q in str(t).lower():
                return True

    return False


def _pet_has_trait(pet: Pet, trait: str) -> bool:
    selected = (trait or "").strip().lower()
    if not selected:
        return True
    try:
        personality = pet.personality
    except Exception:
        return False
    raw_traits = personality.traits
    if isinstance(raw_traits, dict):
        raw_traits = raw_traits.get("list", [])
    if isinstance(raw_traits, list):
        normalized = {str(t).strip().lower() for t in raw_traits if str(t).strip()}
        return selected in normalized
    return False


@require_GET
def home_page(request: HttpRequest) -> HttpResponse:
    selected_tag = (request.GET.get("tag") or "").strip().lower()
    if selected_tag not in DISCOVER_TAG_OPTIONS:
        selected_tag = ""

    public_pets = (
        Pet.objects.filter(visibility=Pet.Visibility.PUBLIC, is_archived=False)
        .select_related("owner", "personality")
        .prefetch_related("assets")
        .order_by("-updated_at")
    )
    if selected_tag:
        public_pets = [p for p in public_pets if _pet_has_trait(p, selected_tag)]
    else:
        public_pets = list(public_pets)

    pet_cards = [_pet_card_data(p) for p in public_pets]
    featured_pets = pet_cards[:18]
    return render(
        request,
        "index.html",
        {
            "featured_pets": featured_pets,
            "available_tags": DISCOVER_TAG_OPTIONS,
            "selected_tag": selected_tag,
        },
    )


@require_GET
def pets_search_page(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    public_pets = (
        Pet.objects.filter(visibility=Pet.Visibility.PUBLIC, is_archived=False)
        .select_related("owner", "personality")
        .prefetch_related("assets")
        .order_by("-updated_at")
    )
    matches = [p for p in public_pets if _pet_matches_search(p, query)]
    results = [_pet_card_data(p) for p in matches]
    return render(
        request,
        "search_results.html",
        {
            "query": query,
            "results": results,
            "result_count": len(results),
        },
    )


@login_required
@require_GET
def create_pet_page(request: HttpRequest) -> HttpResponse:
    return render(request, "create_pet.html")


@login_required
@require_GET
def pet_chat_page(request: HttpRequest, pet_id: int) -> HttpResponse:
    get_object_or_404(Pet, pk=pet_id)
    return render(request, "pet_chat.html", {"pet_id": pet_id})


@require_http_methods(["GET", "POST"])
def auth_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "login":
            email = (request.POST.get("email") or "").strip().lower()
            password = request.POST.get("password") or ""
            user = authenticate(request, email=email, password=password)
            if user is None:
                messages.error(request, "Invalid email or password.")
            elif not user.is_active:
                messages.error(request, "This account is disabled.")
            else:
                login(request, user)
                messages.success(request, f"Welcome back, {user.display_name or user.username}.")
                return redirect("home")
        elif action == "register":
            email = (request.POST.get("email") or "").strip().lower()
            username = (request.POST.get("username") or "").strip()
            password = request.POST.get("password") or ""
            display_name = (request.POST.get("display_name") or "").strip() or None
            if len(password) < 8:
                messages.error(request, "Password must be at least 8 characters.")
            elif not email or not username:
                messages.error(request, "Email and username are required.")
            else:
                try:
                    user = User.objects.create_user(
                        email=email,
                        username=username,
                        password=password,
                        display_name=display_name,
                    )
                except IntegrityError:
                    messages.error(request, "Email or username is already in use.")
                else:
                    login(request, user)
                    messages.success(request, "Account created.")
                    return redirect("home")

    return render(request, "auth.html")


@login_required
@require_http_methods(["POST"])
def logout_page(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.success(request, "Signed out.")
    return redirect("home")


@require_http_methods(["GET", "POST"])
def pets_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to manage pets.")
            return redirect("auth")

        action = (request.POST.get("action") or "").strip()
        if action == "create_pet":
            name = (request.POST.get("name") or "").strip()
            visibility = (request.POST.get("visibility") or Pet.Visibility.PRIVATE).strip()
            if not name:
                messages.error(request, "Pet name is required.")
            else:
                Pet.objects.create(owner=request.user, name=name, visibility=visibility)
                messages.success(request, "Pet created.")
            return redirect("pets")

        pet_id = request.POST.get("pet_id")
        pet = get_object_or_404(Pet, pk=pet_id) if pet_id else None
        can_modify = pet is not None and (pet.owner_id == request.user.id or request.user.is_staff)

        if action == "update_pet":
            if not can_modify:
                messages.error(request, "You cannot edit this pet.")
                return redirect("pets")
            pet.name = (request.POST.get("name") or pet.name).strip() or pet.name
            pet.visibility = (request.POST.get("visibility") or pet.visibility).strip()
            pet.is_archived = request.POST.get("is_archived") == "on"
            pet.save()
            messages.success(request, "Pet updated.")
            return redirect("pets")

        if action == "delete_pet":
            if not can_modify:
                messages.error(request, "You cannot delete this pet.")
                return redirect("pets")
            pet.delete()
            messages.success(request, "Pet deleted.")
            return redirect("pets")

        if action == "create_report":
            if pet is None:
                messages.error(request, "Pet not found.")
                return redirect("pets")
            reason = (request.POST.get("reason") or "").strip()
            details = (request.POST.get("details") or "").strip() or None
            if not reason:
                messages.error(request, "Reason is required.")
            else:
                ModerationReport.objects.create(
                    reporter_user=request.user,
                    pet=pet,
                    reason=reason,
                    details=details,
                )
                messages.success(request, "Report submitted.")
            return redirect("pets")

    my_pets = []
    if request.user.is_authenticated:
        my_pet_qs = (
            Pet.objects.filter(owner=request.user)
            .select_related("owner", "personality")
            .prefetch_related("assets")
            .order_by("-updated_at")
        )
        my_pets = [
            {
                **_pet_card_data(pet),
                "visibility": pet.visibility,
                "updated_at": pet.updated_at,
            }
            for pet in my_pet_qs
        ]

    return render(
        request,
        "pets.html",
        {
            "my_pets": my_pets,
            "my_reports": ModerationReport.objects.filter(reporter_user=request.user).order_by("-created_at")
            if request.user.is_authenticated
            else [],
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def mod_page(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        messages.error(request, "Moderator access required.")
        return redirect("home")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        report_id = request.POST.get("report_id")
        pet_id = request.POST.get("pet_id")

        if action in {"resolve_report", "reject_report"} and report_id:
            report = get_object_or_404(ModerationReport, pk=report_id)
            report.status = (
                ModerationReport.Status.RESOLVED
                if action == "resolve_report"
                else ModerationReport.Status.REJECTED
            )
            if not report.resolved_at:
                from django.utils import timezone

                report.resolved_at = timezone.now()
            report.save()
            messages.success(request, "Report updated.")
            return redirect("mod")

        if action in {"hide_pet", "delete_pet"} and pet_id:
            pet = get_object_or_404(Pet, pk=pet_id)
            if action == "hide_pet":
                pet.visibility = Pet.Visibility.PRIVATE
                pet.is_archived = True
                pet.save()
                messages.success(request, "Pet hidden from public view.")
            else:
                pet.delete()
                messages.success(request, "Pet deleted.")
            return redirect("mod")

    active_reports = ModerationReport.objects.filter(status=ModerationReport.Status.OPEN).order_by("-created_at")
    return render(request, "mod.html", {"active_reports": active_reports})


@login_required
@require_http_methods(["GET", "POST"])
def manage_page(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        messages.error(request, "Administrator access required.")
        return redirect("home")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "update_user":
            user = get_object_or_404(User, pk=request.POST.get("user_id"))
            email = (request.POST.get("email") or "").strip().lower()
            username = (request.POST.get("username") or "").strip()
            display_name = (request.POST.get("display_name") or "").strip() or None

            if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                messages.error(request, "Email already in use.")
                return redirect("manage")
            if username and User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                messages.error(request, "Username already in use.")
                return redirect("manage")

            if email:
                user.email = email
            if username:
                user.username = username
            user.display_name = display_name
            user.is_active = request.POST.get("is_active") == "on"
            user.is_staff = request.POST.get("is_staff") == "on"
            user.is_superuser = request.POST.get("is_superuser") == "on"
            user.save()
            messages.success(request, "User updated.")
            return redirect("manage")

        if action == "delete_user":
            user = get_object_or_404(User, pk=request.POST.get("user_id"))
            if user.id == request.user.id:
                messages.error(request, "You cannot delete your own account.")
            else:
                user.delete()
                messages.success(request, "User deleted.")
            return redirect("manage")

        if action == "update_pet":
            pet = get_object_or_404(Pet, pk=request.POST.get("pet_id"))
            pet.name = (request.POST.get("name") or pet.name).strip() or pet.name
            pet.visibility = (request.POST.get("visibility") or pet.visibility).strip()
            pet.is_archived = request.POST.get("is_archived") == "on"
            pet.save()
            messages.success(request, "Pet updated.")
            return redirect("manage")

        if action == "delete_pet":
            pet = get_object_or_404(Pet, pk=request.POST.get("pet_id"))
            pet.delete()
            messages.success(request, "Pet deleted.")
            return redirect("manage")

        if action in {"resolve_report", "reject_report"}:
            report = get_object_or_404(ModerationReport, pk=request.POST.get("report_id"))
            report.status = (
                ModerationReport.Status.RESOLVED
                if action == "resolve_report"
                else ModerationReport.Status.REJECTED
            )
            if not report.resolved_at:
                from django.utils import timezone

                report.resolved_at = timezone.now()
            report.save()
            messages.success(request, "Report updated.")
            return redirect("manage")

    context = {
        "users": User.objects.all().order_by("-created_at"),
        "pets": Pet.objects.all().order_by("-updated_at"),
        "active_reports": ModerationReport.objects.filter(status=ModerationReport.Status.OPEN).order_by("-created_at"),
    }
    return render(request, "manage.html", context)
