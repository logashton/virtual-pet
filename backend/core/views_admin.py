from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializer import AdminUserSerializer, AdminUserUpdateSerializer


def _is_admin(user):
    return user is not None and user.is_authenticated and user.is_superuser


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response(
                {"detail": "Only administrators can list users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = User.objects.all().order_by("-created_at")
        serializer = AdminUserSerializer(qs, many=True)
        return Response(serializer.data)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _is_admin(request.user):
            return Response({"detail": "Only administrators can view users."}, status=status.HTTP_403_FORBIDDEN)
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminUserSerializer(user).data)

    def patch(self, request, pk):
        if not _is_admin(request.user):
            return Response({"detail": "Only administrators can update users."}, status=status.HTTP_403_FORBIDDEN)
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user).data)

    def delete(self, request, pk):
        if not _is_admin(request.user):
            return Response({"detail": "Only administrators can delete users."}, status=status.HTTP_403_FORBIDDEN)
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if user.id == request.user.id:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
