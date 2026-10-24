"""Compositor: junta as camadas (por zPos) de uma seleção em uma folha LPC de 832x3456."""
from __future__ import annotations

import os
import re

import numpy as np
from PIL import Image

from .catalog import Catalog, Item
from .constants import (ANIM_FOLDER, ANIMS, DEFAULT_ANIMS, FRAME, NO_EXPORT, SHEET_H, SHEET_W)

_cache: dict[str, np.ndarray] = {}


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _load(path: str) -> np.ndarray | None:
    a = _cache.get(path)
    if a is None:
        if not os.path.isfile(path):
            return None
        a = np.array(Image.open(path).convert("RGBA"))
        if len(_cache) > 600:
            _cache.clear()
        _cache[path] = a
    return a


def recolor(arr: np.ndarray, mapping: list[tuple[list[str], list[str]]]) -> np.ndarray:
    """Troca cores exatas (tolerância 1) da paleta de origem para a de destino, índice a índice."""
    if not mapping:
        return arr
    out = arr.copy()
    rgb = arr[..., :3].astype(np.int16)
    solid = arr[..., 3] > 0
    for src, dst in mapping:
        for s, d in zip(src, dst):
            sr = np.array(_hex(s), dtype=np.int16)
            m = solid & (np.abs(rgb - sr).max(axis=-1) <= 1)
            if m.any():
                out[m, 0:3] = _hex(d)
    return out


def body_selection(sel: dict) -> dict | None:
    b = sel.get("body")
    return b if isinstance(b, dict) else None


def color_mapping(cat: Catalog, it: Item, s: dict, body_sel: dict | None, shared: dict | None = None) -> list:
    """Lista de (origem, destino) para esse item, dada a seleção."""
    mapping = []
    rc = s.get("recolor") or s.get("variant") or None
    for slot in it.slots():
        name = None
        if isinstance(rc, dict):
            name = rc.get(slot["key"])
        elif isinstance(rc, str) and slot["key"] == "color_1":
            name = rc
        if slot.get("shared"):                       # cor compartilhada (ex.: cor dos olhos)
            name = (shared or {}).get(slot["shared"]) or cat.color_names(slot)[0]
        elif it.match_body_color and body_sel and slot["material"] == "body":
            brc = body_sel.get("recolor")
            name = brc if isinstance(brc, str) else name
        if not name:
            continue
        src, dst = cat.source_colors(slot), cat.target_colors(slot, name)
        if src and dst:
            mapping.append((src, dst))
    return mapping


def _anims_for(it: Item) -> list[str]:
    names = it.animations or DEFAULT_ANIMS
    out: list[str] = []
    for n in names:
        if n in NO_EXPORT:
            continue
        f = ANIM_FOLDER.get(n, n)
        if f in ANIMS and f not in out:
            out.append(f)
    return out


def tag_ok(it: Item, chosen: list[Item]) -> bool:
    if not it.required_tags:
        return True
    have = {t for o in chosen if o is not it for t in o.tags}
    return all(t in have for t in it.required_tags)


def resolve(cat: Catalog, character: dict) -> tuple[list[tuple[Item, dict]], list[str]]:
    """Itens válidos da seleção (ordem preservada) e avisos."""
    body = character.get("bodyType", "male")
    warns: list[str] = []
    pairs = []
    for key, s in (character.get("selections") or {}).items():
        if not isinstance(s, dict) or not s.get("itemId"):
            continue
        it = cat.items.get(s["itemId"])
        if it is None:
            warns.append(f"Item desconhecido: {s['itemId']}")
        elif not it.supported(body):
            warns.append(f"{it.name}: não existe para esse tipo de corpo")
        else:
            pairs.append((it, s))
    chosen = [p[0] for p in pairs]
    ok = []
    for it, s in pairs:
        if tag_ok(it, chosen):
            ok.append((it, s))
        else:
            warns.append(f"{it.name}: precisa de outra peça ({', '.join(it.required_tags)})")
    return ok, warns


def replace_in_path(cat: Catalog, it: Item, path: str, sels: dict) -> str | None:
    """Troca ${tipo} pelo valor ligado à peça escolhida (ex.: rosto depende da cabeça)."""
    rip = it.replace_in_path or {}
    bad = False

    def sub(m):
        nonlocal bad
        s = sels.get(m.group(1)) or {}
        other = cat.items.get(s.get("itemId", ""))
        rep = rip.get(m.group(1), {}).get(other.name.replace(" ", "_")) if other else None
        if rep is None:
            bad = True
            return ""
        return rep
    out = re.sub(r"\$\{(\w+)\}", sub, path)
    return None if bad else out


def draw_calls(cat: Catalog, character: dict):
    body = character.get("bodyType", "male")
    pairs, warns = resolve(cat, character)
    body_sel = body_selection(character.get("selections") or {})
    shared = character.get("shared") or {}
    sels = character.get("selections") or {}
    calls = []
    order = 0
    for it, s in pairs:
        mapping = color_mapping(cat, it, s, body_sel, shared)
        variant = (s.get("variant") or "").replace(" ", "_")
        if not variant and not it.recolors and it.variants:
            variant = it.variants[0].replace(" ", "_")
        for lay in it.layers:
            if lay["custom"] or lay["mask"] or body not in lay["paths"]:
                continue
            for folder in _anims_for(it):
                base = lay["paths"][body]
                if "${" in base:
                    base = replace_in_path(cat, it, base, sels)
                    if base is None:
                        continue
                p = os.path.join(cat.root, "spritesheets", base + folder
                                 + ("" if it.recolors else "/" + variant) + ".png")
                calls.append((lay["zPos"], order, folder, p, mapping))
                order += 1
    calls.sort(key=lambda c: (c[0], c[1]))
    return calls, warns


def render_sheet(cat: Catalog, character: dict, only: set[str] | None = None) -> tuple[Image.Image, list[str]]:
    calls, warns = draw_calls(cat, character)
    canvas = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    for _z, _o, folder, path, mapping in calls:
        if only and folder not in only:
            continue
        arr = _load(path)
        if arr is None:
            continue
        im = Image.fromarray(recolor(arr, mapping))
        canvas.alpha_composite(im, (0, ANIMS[folder][0] * FRAME))
    return canvas, warns
