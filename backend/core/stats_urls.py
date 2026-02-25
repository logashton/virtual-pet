from django.urls import path
from . import views_stats

urlpatterns = [
    path("<int:pk>/stats/", views_stats.PetStatsView.as_view(), name="pet_stats"),
    path("<int:pk>/action/", views_stats.PetActionView.as_view(), name="pet_action"),
]
