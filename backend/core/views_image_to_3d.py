import io

import numpy as np
from PIL import Image
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shapely.geometry import Polygon
from skimage import measure


def _ensure_rgba(image_bytes):
    inp = Image.open(io.BytesIO(image_bytes))
    if inp.mode not in ("RGB", "RGBA"):
        inp = inp.convert("RGB")
    if inp.mode != "RGBA":
        from rembg import remove
        inp = remove(inp)
    buf = io.BytesIO()
    inp.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _image_to_glb(png_bytes):
    import trimesh

    img = Image.open(io.BytesIO(png_bytes))
    img = img.convert("RGBA")
    rgba = np.array(img)
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0

    contours = measure.find_contours(alpha, 0.5)
    if not contours:
        raise ValueError("No contour found (empty or fully transparent image)")

    def area(c):
        poly = Polygon(c)
        return abs(poly.area) if not poly.is_empty else 0

    contour = max(contours, key=area)
    pts = np.column_stack([contour[:, 1], contour[:, 0]])

    if len(pts) > 400:
        from shapely.geometry import LineString
        line = LineString(pts)
        simplified = line.simplify(tolerance=2.0, preserve_topology=True)
        if simplified.geom_type == "LineString":
            pts = np.array(simplified.coords)
        elif simplified.geom_type == "MultiLineString":
            longest = max(simplified.geoms, key=lambda g: g.length)
            pts = np.array(longest.coords)

    try:
        poly = Polygon(pts)
    except Exception:
        raise ValueError("Invalid polygon from contour")
    if poly.is_empty or not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        raise ValueError("Contour produced empty polygon")

    height = max(min(w, h) * 0.08, 4.0)
    mesh = trimesh.creation.extrude_polygon(poly, height=height, engine="earcut")

    verts = mesh.vertices.copy()
    u = np.clip(verts[:, 0] / w, 0, 1)
    v = np.clip(1.0 - verts[:, 1] / h, 0, 1)
    uv = np.column_stack([u, v]).astype(np.float64)

    mesh.vertices -= mesh.centroid
    ext = np.max(mesh.extents)
    if ext > 1e-6:
        mesh.vertices /= ext

    x, y, z = mesh.vertices[:, 0].copy(), mesh.vertices[:, 1].copy(), mesh.vertices[:, 2].copy()
    mesh.vertices[:, 0], mesh.vertices[:, 1], mesh.vertices[:, 2] = x, z, -y

    mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=img)
    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return buf.getvalue()


class ImageTo3DView(APIView):
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
            png_bytes = _ensure_rgba(raw)
            glb_bytes = _image_to_glb(png_bytes)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"detail": "3D conversion failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        from django.http import HttpResponse
        response = HttpResponse(glb_bytes, content_type="model/gltf-binary")
        response["Content-Disposition"] = 'inline; filename="image-3d.glb"'
        return response
