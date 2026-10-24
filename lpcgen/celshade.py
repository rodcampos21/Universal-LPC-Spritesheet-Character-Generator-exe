"""EXPERIMENTAL: versão HD com 'cel shade' (contorno de tinta, bordas suaves, cores chapadas) a partir da pixel art."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

DEFAULTS = {"scale": 3, "smooth": 60, "outline": 2, "ink": True, "bands": 0, "saturation": 110}
OUTLINE_PX = {0: 0, 1: 1, 2: 2, 3: 3}                      # nenhum / fino / médio / grosso (em px do HD, × escala/3)


def clean(params: dict | None) -> dict:
    p = dict(DEFAULTS)
    for k, v in (params or {}).items():
        if k in p:
            p[k] = v
    p["scale"] = p["scale"] if p["scale"] in (2, 3, 4) else 3
    p["smooth"] = max(0, min(100, int(p["smooth"])))
    p["outline"] = max(0, min(3, int(p["outline"])))
    p["bands"] = 0 if int(p["bands"]) < 2 else min(8, int(p["bands"]))
    p["saturation"] = max(50, min(200, int(p["saturation"])))
    p["ink"] = bool(p["ink"])
    return p


def _key(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.uint32)
    return (a[..., 0] << 24) | (a[..., 1] << 16) | (a[..., 2] << 8) | a[..., 3]


def epx(a: np.ndarray) -> np.ndarray:
    """Scale2x/EPX: dobra o tamanho suavizando diagonais, sem inventar cores."""
    k = np.pad(_key(a), 1)
    p = np.pad(a, ((1, 1), (1, 1), (0, 0)))
    P, A, B, C, D = (p[1:-1, 1:-1], p[:-2, 1:-1], p[1:-1, 2:], p[1:-1, :-2], p[2:, 1:-1])
    kp, ka, kb, kc, kd = (k[1:-1, 1:-1], k[:-2, 1:-1], k[1:-1, 2:], k[1:-1, :-2], k[2:, 1:-1])
    c1 = (kc == ka) & (kc != kd) & (ka != kb)
    c2 = (ka == kb) & (ka != kc) & (kb != kd)
    c3 = (kd == kc) & (kd != kb) & (kc != ka)
    c4 = (kb == kd) & (kb != ka) & (kd != kc)
    h, w = a.shape[:2]
    out = np.empty((2 * h, 2 * w, 4), np.uint8)
    out[0::2, 0::2] = np.where(c1[..., None], A, P)
    out[0::2, 1::2] = np.where(c2[..., None], B, P)
    out[1::2, 0::2] = np.where(c3[..., None], C, P)
    out[1::2, 1::2] = np.where(c4[..., None], D, P)
    return out


def _upscale(a: np.ndarray, scale: int) -> np.ndarray:
    if scale == 2:
        return epx(a)
    if scale == 4:
        return epx(epx(a))
    return np.repeat(np.repeat(a, 3, axis=0), 3, axis=1)


def celshade_frame(im: Image.Image, params: dict | None = None) -> Image.Image:
    """Um quadro RGBA → quadro HD (tamanho × escala). A margem é processada para o contorno não ser cortado."""
    p = clean(params)
    s = p["scale"]
    w, h = im.size
    pad = 4
    base = Image.new("RGBA", (w + 2 * pad, h + 2 * pad))
    base.paste(im.convert("RGBA"), (pad, pad))
    a = _upscale(np.array(base), s)
    img = Image.fromarray(a)
    k = max(1, round(s * p["smooth"] / 100 * 0.6))
    if p["smooth"] > 0:
        # cores: suaviza serrilhado (mediana) sem borrar as áreas chapadas
        rgb = img.convert("RGB").filter(ImageFilter.MedianFilter(3 if s <= 3 else 5))
        alpha = img.getchannel("A").filter(ImageFilter.GaussianBlur(k))
        al = np.clip((np.array(alpha).astype(np.float32) / 255 - 0.5) * 3.0 + 0.5, 0, 1)   # borda macia e redonda
        # evita franja escura: espalha a cor do sprite para fora do contorno
        c = np.array(rgb).astype(np.float32)
        am = (a[..., 3] > 0).astype(np.float32)
        num = np.array(Image.fromarray((c * am[..., None]).astype(np.uint8)).filter(ImageFilter.GaussianBlur(k + 1))).astype(np.float32)
        den = np.array(Image.fromarray((am * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(k + 1))).astype(np.float32)[..., None] / 255
        spread = np.where(den > 0.02, num / np.maximum(den, 0.02), c)
        c = np.where(am[..., None] > 0, c, np.clip(spread, 0, 255))
        col = np.clip(c, 0, 255)
    else:
        al = a[..., 3].astype(np.float32) / 255
        col = a[..., :3].astype(np.float32)
    # contraste/saturação
    lum = (col * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=-1, keepdims=True)
    col = np.clip(lum + (col - lum) * (p["saturation"] / 100), 0, 255)
    # bandas de sombra (cel shade): poucos níveis de brilho, mantendo o matiz
    if p["bands"]:
        lum = (col * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=-1, keepdims=True)
        v = np.maximum(lum, 1) / 255
        q = np.round(v * (p["bands"] - 1)) / (p["bands"] - 1)
        col = np.clip(col * (np.maximum(q, 0.08) / v), 0, 255)
    # linhas internas de tinta (onde o tom muda bruscamente)
    if p["ink"]:
        lum = (col * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=-1)
        gy, gx = np.gradient(lum)
        g = np.hypot(gx, gy)
        line = np.clip((g - 6.0) / 18.0, 0, 1) * (al > 0.8)
        col = col * (1 - 0.45 * line[..., None])
    out = np.dstack([col, al * 255]).astype(np.uint8)
    res = Image.fromarray(out, "RGBA")
    # contorno externo (tinta)
    t = OUTLINE_PX[p["outline"]]
    if t:
        t = max(1, round(t * s / 3))
        mask = res.getchannel("A").point(lambda v: 255 if v > 100 else 0)
        dil = mask.filter(ImageFilter.MaxFilter(2 * t + 1))
        ring = np.array(dil).astype(np.int16) - np.array(mask).astype(np.int16)
        ring = np.clip(ring, 0, 255).astype(np.uint8)
        # cor da tinta: tom bem escuro do próprio sprite (fica mais bonito que preto puro)
        ink = Image.new("RGBA", res.size, (22, 14, 26, 0))
        ink.putalpha(Image.fromarray(ring).filter(ImageFilter.GaussianBlur(0.6)))
        res = Image.alpha_composite(ink, res)
    crop = (pad * s, pad * s, (pad + w) * s, (pad + h) * s)
    return res.crop(crop)


def celshade_sheet(sheet: Image.Image, cell: int, params: dict | None = None) -> Image.Image:
    """Aplica quadro a quadro numa folha de células cell×cell. Células vazias são puladas."""
    p = clean(params)
    s = p["scale"]
    cols, rows = sheet.width // cell, sheet.height // cell
    out = Image.new("RGBA", (cols * cell * s, rows * cell * s))
    for r in range(rows):
        for c in range(cols):
            fr = sheet.crop((c * cell, r * cell, (c + 1) * cell, (r + 1) * cell))
            if fr.getbbox() is None:
                continue
            out.paste(celshade_frame(fr, p), (c * cell * s, r * cell * s))
    return out
