from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ModerationReport
from .serializer import (
    ModerationReportCreateSerializer,
    ModerationReportSerializer,
    ModerationReportUpdateSerializer,
)


class ModerationReportListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pet_id = request.query_params.get("pet")
        if pet_id and not request.user.is_staff:
            return Response(
                {"detail": "Only moderators can view all reports for a pet."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = ModerationReport.objects.all().order_by("-created_at")
        if not request.user.is_staff:
            qs = qs.filter(reporter_user=request.user)
        if pet_id:
            try:
                qs = qs.filter(pet_id=int(pet_id))
            except ValueError:
                pass
        status_param = request.query_params.get("status", "").strip().lower()
        if status_param and status_param in (ModerationReport.Status.OPEN, ModerationReport.Status.RESOLVED, ModerationReport.Status.REJECTED):
            qs = qs.filter(status=status_param)
        serializer = ModerationReportSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ModerationReportCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(ModerationReportSerializer(report).data, status=status.HTTP_201_CREATED)


class ModerationReportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_report(self, pk):
        try:
            return ModerationReport.objects.get(pk=pk)
        except ModerationReport.DoesNotExist:
            return None

    def get(self, request, pk):
        report = self._get_report(pk)
        if not report:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_staff and report.reporter_user_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ModerationReportSerializer(report).data)

    def patch(self, request, pk):
        report = self._get_report(pk)
        if not report:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_staff:
            return Response({"detail": "Only staff can update reports."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ModerationReportUpdateSerializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        if report.status != ModerationReport.Status.OPEN and not report.resolved_at:
            report.resolved_at = timezone.now()
            report.save()
        return Response(ModerationReportSerializer(report).data)

    def delete(self, request, pk):
        report = self._get_report(pk)
        if not report:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_staff:
            return Response({"detail": "Only staff can delete reports."}, status=status.HTTP_403_FORBIDDEN)
        report.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
