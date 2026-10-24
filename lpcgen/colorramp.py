"""Cores livres: gera uma paleta de 6 tons (sombra → luz) a partir de uma cor, como as paletas do LPC."""
from __future__ import annotations


def parse(hexcolor: str) -> tuple[int, int, int] | None:
    h = (hexcolor or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def ramp(hexcolor: str) -> list[str] | None:
    rgb = parse(hexcolor)
    if rgb is None:
        return None
    r, g, b = rgb
    out = []
    for f in (0.30, 0.50, 0.75, 1.0):                          # sombras: escurece (um pouco mais quente)
        k = f
        out.append((r * k * (1.0 if f == 1.0 else 1.04), g * k, b * k * (1.0 if f == 1.0 else 0.92)))
    for t in (0.22, 0.42):                                      # luzes: mistura com branco
        out.append((r + (255 - r) * t, g + (255 - g) * t, b + (255 - b) * t))
    return ["#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c) for c in out]
