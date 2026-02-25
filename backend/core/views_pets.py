import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pet, PetAsset
from .serializer import PetCreateSerializer, PetSerializer, PetUpdateSerializer


def _can_read_pet(pet, user):
    if pet.visibility == Pet.Visibility.PRIVATE:
        return user is not None and user.is_authenticated and pet.owner_id == user.id
    return True


def _is_owner(pet, user):
    return user is not None and user.is_authenticated and pet.owner_id == user.id


def _can_modify_pet(pet, user):
    return _is_owner(pet, user) or (user is not None and user.is_authenticated and user.is_staff)


class PetListCreateView(APIView):
    #scope=mine requires auth, scope=public lists public pets). 

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return []

    def get(self, request):
        scope = (request.query_params.get("scope") or "").strip().lower()
        if scope == "mine":
            if not request.user.is_authenticated:
                return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            qs = Pet.objects.filter(owner=request.user).order_by("-updated_at")
        elif scope == "public":
            qs = Pet.objects.filter(visibility=Pet.Visibility.PUBLIC, is_archived=False).order_by("-updated_at")
        elif scope == "all":
            if not request.user.is_authenticated or not request.user.is_superuser:
                return Response(
                    {"detail": "Only administrators can list all pets."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            qs = Pet.objects.all().order_by("-updated_at")
        else:
            # Default for authenticated: my pets. For anonymous: require scope=public
            if request.user.is_authenticated:
                qs = Pet.objects.filter(owner=request.user).order_by("-updated_at")
            else:
                return Response(
                    {"detail": "Use scope=mine (authenticated) or scope=public."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer = PetSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PetCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        pet = serializer.save()
        return Response(PetSerializer(pet).data, status=status.HTTP_201_CREATED)


class PetDetailView(APIView):
    def get(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_read_pet(pet, request.user):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PetSerializer(pet).data)

    def patch(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_modify_pet(pet, request.user):
            return Response({"detail": "Only the owner or a moderator can update this pet."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PetUpdateSerializer(pet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        pet = serializer.save()
        return Response(PetSerializer(pet).data)

    def delete(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_modify_pet(pet, request.user):
            return Response({"detail": "Only the owner or a moderator can delete this pet."}, status=status.HTTP_403_FORBIDDEN)
        pet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PetUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if not _can_modify_pet(pet, request.user):
            return Response(
                {"detail": "Only the owner or a moderator can upload images for this pet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        image = request.FILES.get("image")
        if not image:
            return Response({"detail": "Missing image file field: image"}, status=status.HTTP_400_BAD_REQUEST)

        ext = (image.name.rsplit(".", 1)[-1].lower() if "." in image.name else "jpg") or "jpg"
        rel_path = f"uploads/pets/{pet.id}/{uuid.uuid4().hex}.{ext}"
        saved_path = default_storage.save(rel_path, image)
        image_url = settings.MEDIA_URL + saved_path

        asset = PetAsset.objects.create(
            pet=pet,
            original_image_url=image_url,
            cutout_image_url=None,
            model_3d_url=None,
            asset_type=PetAsset.AssetType.IMAGE,
            status=PetAsset.Status.READY,
        )

        return Response(
            {
                "id": asset.id,
                "pet_id": pet.id,
                "original_image_url": asset.original_image_url,
                "status": asset.status,
            },
            status=status.HTTP_201_CREATED,
        )
