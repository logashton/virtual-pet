from django.urls import path

from . import views_moderation

urlpatterns = [
    path("", views_moderation.ModerationReportListCreateView.as_view(), name="moderation_report_list_create"),
    path("<int:pk>/", views_moderation.ModerationReportDetailView.as_view(), name="moderation_report_detail"),
]
