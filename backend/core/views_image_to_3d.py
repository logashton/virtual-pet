import io

import numpy as np
from PIL import Image
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shapely.geometry import Polygon
from skimage import measure
from skimage.transform import resize as skresize


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


def _get_depth_map(rgb_pil, target_size):
    try:
        from transformers import pipeline
    except ImportError:
        return None
    try:
        pipe = pipeline(
            "depth-estimation",
            model="depth-anything/Depth-Anything-V2-Small-hf",
        )
    except Exception:
        return None
    try:
        out = pipe(rgb_pil)
        pred = out.get("predicted_depth")
        if pred is not None:
            import torch
            depth = pred.cpu().numpy().squeeze().astype(np.float64)
        else:
            depth_pil = out.get("depth")
            if depth_pil is None:
                return None
            depth = np.array(depth_pil, dtype=np.float64)
    except Exception:
        return None
    if depth.size == 0:
        return None
    depth = depth - np.nanmin(depth)
    mx = np.nanmax(depth)
    if mx > 1e-9:
        depth = depth / mx
    h, w = target_size[1], target_size[0]
    if depth.shape[0] != h or depth.shape[1] != w:
        depth = skresize(depth, (h, w), order=1, preserve_range=True, anti_aliasing=True)
    return np.clip(depth, 0, 1).astype(np.float32)


def _synthetic_depth(rgba, alpha):
    """Fallback depth from luminance * alpha so we always have some relief."""
    rgb = rgba[:, :, :3].astype(np.float32) / 255.0
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    lum = lum * alpha
    lo, hi = np.nanmin(lum), np.nanmax(lum)
    if hi - lo > 1e-9:
        lum = (lum - lo) / (hi - lo)
    return np.clip(lum.astype(np.float32), 0, 1)


def _relief_mesh_to_glb(img, rgba, depth, alpha, grid_res=80):
    """Build a depth-displaced (relief) mesh and return GLB bytes."""
    import trimesh

    h, w = rgba.shape[:2]
    yy, xx = np.where(alpha >= 0.1)
    if yy.size == 0:
        return None
    min_r, max_r = int(yy.min()), int(yy.max()) + 1
    min_c, max_c = int(xx.min()), int(xx.max()) + 1
    box_h, box_w = max_r - min_r, max_c - min_c
    nhy = max(2, min(grid_res, box_h))
    nhx = max(2, min(grid_res, int(grid_res * box_w / max(box_h, 1))))
    nhy = max(2, min(nhy, 120))
    nhx = max(2, min(nhx, 120))

    # Vertex positions and UVs
    xs = np.linspace(min_c, max_c, nhx, dtype=np.float32)
    ys = np.linspace(min_r, max_r, nhy, dtype=np.float32)
    # Sample alpha and depth at grid points (row, col)
    alpha_flat = alpha
    depth_flat = depth
    # Depth scale: make displacement a visible fraction of bbox size (in pixel units)
    depth_scale = 0.15 * max(box_w, box_h)

    verts_list = []
    uv_list = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            c, r = int(round(x)), int(round(y))
            c = np.clip(c, 0, w - 1)
            r = np.clip(r, 0, h - 1)
            a = alpha_flat[r, c]
            d = depth_flat[r, c] if depth_flat is not None else 0.0
            z = d * a * depth_scale
            verts_list.append([x, y, z])
            uv_list.append([x / w, 1.0 - y / h])

    verts = np.array(verts_list, dtype=np.float64)
    uv = np.array(uv_list, dtype=np.float64)
    uv = np.clip(uv, 0, 1)

    # Build alpha per vertex (same order as verts) for face culling
    alpha_at_vertex = np.array([
        alpha_flat[np.clip(int(round(ys[j])), 0, h - 1), np.clip(int(round(xs[i])), 0, w - 1)]
        for j in range(nhy) for i in range(nhx)
    ], dtype=np.float32)

    # Faces: only add quads where all 4 corners are inside the subject (avoids vertical "spikes" at silhouette)
    INSIDE_ALPHA = 0.45
    faces = []
    for j in range(nhy - 1):
        for i in range(nhx - 1):
            a = j * nhx + i
            b = a + 1
            c = a + nhx
            d = c + 1
            if (alpha_at_vertex[a] >= INSIDE_ALPHA and alpha_at_vertex[b] >= INSIDE_ALPHA and
                    alpha_at_vertex[c] >= INSIDE_ALPHA and alpha_at_vertex[d] >= INSIDE_ALPHA):
                faces.append([a, c, b])
                faces.append([b, c, d])
    if not faces:
        return None
    faces = np.array(faces, dtype=np.int32)

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, image=img)

    mesh.vertices -= mesh.centroid
    # Scale XY to fit in 1 unit, but keep depth (Z) proportion visible
    ext_x, ext_y, ext_z = mesh.extents
    scale_xy = 1.0 / max(ext_x, ext_y, 1e-9)
    mesh.vertices[:, 0] *= scale_xy
    mesh.vertices[:, 1] *= scale_xy
    # Depth (Z): scale same as XY, then set relief height to a clear fraction of mesh width
    mesh.vertices[:, 2] *= scale_xy
    depth_boost = 0.45  # relief height as fraction of mesh width (clearly visible)
    z_range = np.ptp(mesh.vertices[:, 2])
    if z_range > 1e-9:
        mesh.vertices[:, 2] *= (depth_boost / z_range)
    else:
        # Uniform depth: give a slight dome so it's not perfectly flat (use vertex distance from center)
        cx, cy = np.mean(mesh.vertices[:, 0]), np.mean(mesh.vertices[:, 1])
        r = np.sqrt((mesh.vertices[:, 0] - cx) ** 2 + (mesh.vertices[:, 1] - cy) ** 2)
        r = r / (np.max(r) + 1e-9)
        mesh.vertices[:, 2] = (1.0 - r) * depth_boost

    # Z-up -> Y-up for Three.js
    x, y, z = mesh.vertices[:, 0].copy(), mesh.vertices[:, 1].copy(), mesh.vertices[:, 2].copy()
    mesh.vertices[:, 0], mesh.vertices[:, 1], mesh.vertices[:, 2] = x, z, -y

    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    buf.seek(0)
    return buf.getvalue()


def _image_to_glb(png_bytes):
    import trimesh

    img = Image.open(io.BytesIO(png_bytes))
    img = img.convert("RGBA")
    rgba = np.array(img)
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0

    # Prefer depth-based relief (from model or synthetic)
    rgb_pil = img.convert("RGB")
    depth = _get_depth_map(rgb_pil, (w, h))
    if depth is None:
        depth = _synthetic_depth(rgba, alpha)
    glb = _relief_mesh_to_glb(img, rgba, depth, alpha)
    if glb is not None:
        return glb

    # Fallback: flat extrusion from contour
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
