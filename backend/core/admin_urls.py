from django.urls import path

from . import views_admin

urlpatterns = [
    path("users/", views_admin.AdminUserListView.as_view(), name="admin_user_list"),
    path("users/<int:pk>/", views_admin.AdminUserDetailView.as_view(), name="admin_user_detail"),
]
