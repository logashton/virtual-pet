"""Tests for image-to-3d API. Mocks rembg and mesh generation to avoid heavy deps."""
import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import User


def _minimal_image_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="blue").save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


class ImageTo3DTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="i3d@test.com",
            username="i3duser",
            password="p",
        )

    def test_image_to_3d_requires_auth(self):
        raw = _minimal_image_bytes()
        f = SimpleUploadedFile("img.png", raw, content_type="image/png")
        resp = self.client.post("/api/image-to-3d/", {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_image_to_3d_missing_image(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post("/api/image-to-3d/", {}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("core.views_image_to_3d._image_to_glb")
    @patch("core.views_image_to_3d._ensure_rgba")
    def test_image_to_3d_success_returns_glb(self, mock_ensure, mock_glb):
        mock_ensure.return_value = b"fake png bytes"
        mock_glb.return_value = b"fake glb binary"
        self.client.force_authenticate(user=self.user)
        raw = _minimal_image_bytes()
        f = SimpleUploadedFile("photo.png", raw, content_type="image/png")
        resp = self.client.post("/api/image-to-3d/", {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "model/gltf-binary")
        self.assertEqual(resp.content, b"fake glb binary")
        mock_ensure.assert_called_once()
        mock_glb.assert_called_once()
