"""Tests for remove-background API. Mocks rembg to avoid heavy deps in test run."""
import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import User


def _minimal_image_bytes(format="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


class RemoveBackgroundTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="bg@test.com",
            username="bguser",
            password="p",
        )

    def test_remove_background_requires_auth(self):
        raw = _minimal_image_bytes()
        f = SimpleUploadedFile("img.png", raw, content_type="image/png")
        resp = self.client.post("/api/remove-background/", {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_remove_background_missing_image(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post("/api/remove-background/", {}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", resp.data)

    @patch("core.views_background._remove_background")
    def test_remove_background_success_returns_png(self, mock_remove):
        mock_remove.return_value = b"\x89PNG\r\n\x1a\n fake png"
        self.client.force_authenticate(user=self.user)
        raw = _minimal_image_bytes()
        f = SimpleUploadedFile("photo.png", raw, content_type="image/png")
        resp = self.client.post("/api/remove-background/", {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertEqual(resp.content, b"\x89PNG\r\n\x1a\n fake png")
        mock_remove.assert_called_once()
