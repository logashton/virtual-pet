from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth_register"),
    path("login/", views.LoginView.as_view(), name="auth_login"),
    path("me/", views.CurrentUserView.as_view(), name="auth_me"),
]
