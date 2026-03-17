import io

from PIL import Image
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


def _remove_background(image_bytes):
    from rembg import remove
    inp = Image.open(io.BytesIO(image_bytes))
    if inp.mode not in ("RGB", "RGBA"):
        inp = inp.convert("RGB")
    out = remove(inp)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


class RemoveBackgroundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"detail": "Missing 'image' file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            raw = image_file.read()
        except Exception:
            return Response(
                {"detail": "Could not read image."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            Image.open(io.BytesIO(raw)).verify()
        except Exception:
            return Response(
                {"detail": "Invalid or unsupported image."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            png_bytes = _remove_background(raw)
        except Exception:
            return Response(
                {"detail": "Background removal failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        from django.http import HttpResponse
        response = HttpResponse(png_bytes, content_type="image/png")
        response["Content-Disposition"] = 'inline; filename="cutout.png"'
        return response
