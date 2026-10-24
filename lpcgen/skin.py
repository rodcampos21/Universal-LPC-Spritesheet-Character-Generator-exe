"""EXPERIMENTAL: sugere cores (pele, cabelo, camisa, calça, sapatos) a partir de uma imagem de personagem."""
from __future__ import annotations

import numpy as np
from PIL import Image


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def _subject_mask(im: Image.Image) -> np.ndarray:
    a = np.array(im.convert("RGBA"))
    if (a[..., 3] < 250).mean() > 0.02:                         # tem transparência
        return a[..., 3] > 128
    corners = np.array([a[0, 0, :3], a[0, -1, :3], a[-1, 0, :3], a[-1, -1, :3]], dtype=np.int16)
    bg = np.median(corners, axis=0)
    return np.abs(a[..., :3].astype(np.int16) - bg).max(axis=-1) > 40


def _is_skin(px: np.ndarray) -> np.ndarray:
    r, g, b = (px[:, 0].astype(int), px[:, 1].astype(int), px[:, 2].astype(int))
    mx, mn = px.max(axis=1).astype(int), px.min(axis=1).astype(int)
    return (r > 95) & (g > 40) & (b > 20) & (mx - mn > 12) & (r > g) & (r > b) & (np.abs(r - g) > 8) & (r < 252)


def _clusters(px: np.ndarray, k: int = 4) -> list[tuple[tuple, float]]:
    """[(cor, fração)] das cores mais comuns (quantização por mediana)."""
    if len(px) == 0:
        return []
    n = min(len(px), 20000)
    sel = px[np.linspace(0, len(px) - 1, n).astype(int)]
    im = Image.fromarray(sel.reshape(1, -1, 3).astype(np.uint8), "RGB")
    q = im.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    out = []
    for cnt, idx in sorted(q.getcolors(), reverse=True):
        out.append(((pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]), cnt / n))
    return out


def _dist(a, b) -> float:
    return float(np.linalg.norm(np.array(a, float) - np.array(b, float)))


def extract(im: Image.Image) -> dict:
    im = im.convert("RGBA")
    if max(im.size) > 800:
        im.thumbnail((800, 800))
    mask = _subject_mask(im)
    if mask.sum() < 50:
        raise ValueError("Não encontrei o personagem na imagem (use fundo liso ou transparente).")
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = np.array(im)[y0:y1, x0:x1, :3]
    m = mask[y0:y1, x0:x1]
    H = rgb.shape[0]

    def band(a, b, skin=None):
        sub = rgb[int(H * a):max(int(H * a) + 1, int(H * b))]
        mm = m[int(H * a):max(int(H * a) + 1, int(H * b))]
        px = sub[mm]
        if skin is not None and len(px):
            keep = _is_skin(px) == skin
            if keep.sum() > 10:
                px = px[keep]
        if len(px):                                   # ignora contornos escuros e brilhos estourados
            lum = px.astype(int).sum(axis=1) / 3
            keep = (lum > 55) & (lum < 245)
            if keep.sum() > 10:
                px = px[keep]
        return px

    # acha o rosto: primeiro bloco de linhas com pele
    skin_rows = np.zeros(H, bool)
    for y in range(H):
        px = rgb[y][m[y]]
        skin_rows[y] = len(px) > 0 and _is_skin(px).sum() >= max(4, 0.04 * m.shape[1])
    face_top, face_bot = None, None
    for y in range(H):
        if skin_rows[y] and face_top is None:
            face_top = y
        if face_top is not None:
            if skin_rows[y]:
                face_bot = y
            elif y - (face_bot or y) > max(2, H * 0.03):
                break
    if face_top is None or face_bot is None or face_bot - face_top < 3:
        face_top, face_bot = int(H * 0.06), int(H * 0.22)                 # sem rosto claro: proporções comuns
    fh = face_bot - face_top
    skin_px = rgb[face_top:face_bot + 1][m[face_top:face_bot + 1]]
    skin_px = skin_px[_is_skin(skin_px)] if len(skin_px) else skin_px
    if len(skin_px) < 10:
        allpx = rgb[m]
        skin_px = allpx[_is_skin(allpx)] if len(allpx) else allpx
    skin = _clusters(skin_px, 3)[0][0] if len(skin_px) else (226, 178, 140)
    out, secondary = {"skin": skin}, {}
    R = max(1, H - face_bot)
    bands = {"hair": (0, face_top + 0.35 * fh), "shirt": (face_bot + 0.05 * R, face_bot + 0.40 * R),
             "pants": (face_bot + 0.45 * R, face_bot + 0.85 * R), "shoes": (face_bot + 0.90 * R, H)}
    for key, (a_, b_) in bands.items():
        out_px = band(a_ / H, b_ / H, False)
        cl = _clusters(out_px, 4) if len(out_px) else []
        if not cl:
            cl = _clusters(band(a_ / H, b_ / H), 4) or [((120, 120, 120), 1.0)]
        out[key] = cl[0][0]
        sec = next((c for c, _f in cl[1:] if _dist(c, cl[0][0]) > 45), None)
        secondary[key] = sec or tuple(min(255, int(v * 1.5) + 20) for v in cl[0][0])
    allpx = rgb[m]
    palette = [{"hex": _hex(c), "pct": round(f * 100)} for c, f in _clusters(allpx, 8)]
    return {"suggest": {k: _hex(v) for k, v in out.items()},
            "secondary": {k: _hex(v) for k, v in secondary.items()}, "palette": palette}
