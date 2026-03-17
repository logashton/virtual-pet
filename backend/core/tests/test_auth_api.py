"""Tests for auth API: register, login, me."""
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import User


class AuthRegisterTest(APITestCase):
    def test_register_success(self):
        resp = self.client.post(
            "/api/auth/register/",
            {"email": "new@example.com", "username": "newuser", "password": "password123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", resp.data)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["user"]["email"], "new@example.com")
        self.assertEqual(resp.data["user"]["username"], "newuser")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_register_duplicate_email(self):
        User.objects.create_user(email="taken@example.com", username="taken", password="p")
        resp = self.client.post(
            "/api/auth/register/",
            {"email": "taken@example.com", "username": "other", "password": "password123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password(self):
        resp = self.client.post(
            "/api/auth/register/",
            {"email": "a@b.com", "username": "u", "password": "short"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AuthLoginTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="login@example.com",
            username="loginuser",
            password="secret123",
        )

    def test_login_success(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"email": "login@example.com", "password": "secret123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["user"]["email"], "login@example.com")

    def test_login_wrong_password(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"email": "login@example.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthMeTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="me@example.com",
            username="meuser",
            password="p",
        )

    def test_me_requires_auth(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_success(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], "me@example.com")
        self.assertEqual(resp.data["username"], "meuser")
