from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pet
from .serializer import PetCreateSerializer, PetSerializer, PetUpdateSerializer


def _can_read_pet(pet, user):
    if pet.visibility == Pet.Visibility.PRIVATE:
        return user is not None and user.is_authenticated and pet.owner_id == user.id
    return True


def _is_owner(pet, user):
    return user is not None and user.is_authenticated and pet.owner_id == user.id


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
        if not _is_owner(pet, request.user):
            return Response({"detail": "Only the owner can update this pet."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PetUpdateSerializer(pet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        pet = serializer.save()
        return Response(PetSerializer(pet).data)

    def delete(self, request, pk):
        try:
            pet = Pet.objects.get(pk=pk)
        except Pet.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _is_owner(pet, request.user):
            return Response({"detail": "Only the owner can delete this pet."}, status=status.HTTP_403_FORBIDDEN)
        pet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
