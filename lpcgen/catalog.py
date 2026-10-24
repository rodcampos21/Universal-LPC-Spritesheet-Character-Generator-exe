"""Lê sheet_definitions/ e palette_definitions/ da arte do LPC e monta o catálogo de itens."""
from __future__ import annotations

import json
import os
from functools import lru_cache

from .constants import BODY_TYPES


class Item:
    def __init__(self, item_id: str, d: dict, rel: str):
        self.id = item_id
        self.name = d.get("name", item_id)
        self.type_name = d.get("type_name", "")
        self.group = rel.split("/")[0] if "/" in rel else "outros"
        self.sub = "/".join(rel.split("/")[:-1])
        self.priority = d.get("priority", 100)
        self.animations = d.get("animations") or None
        self.variants = list(d.get("variants") or [])
        self.recolors = d.get("recolors")
        self.match_body_color = bool(d.get("match_body_color"))
        self.tags = list(d.get("tags") or [])
        self.required_tags = list(d.get("required_tags") or [])
        self.replace_in_path = d.get("replace_in_path")
        self.credits = d.get("credits") or []
        self.layers = []
        for k in sorted((k for k in d if k.startswith("layer_")), key=lambda s: int(s.split("_")[1])):
            lay = d[k]
            self.layers.append({
                "zPos": lay.get("zPos", 100), "custom": lay.get("custom_animation"),
                "mask": bool(lay.get("is_mask")),
                "paths": {b: lay[b] for b in BODY_TYPES if isinstance(lay.get(b), str)},
            })

    def uses_replace(self) -> bool:
        return any("${" in p for l in self.layers for p in l["paths"].values())

    def supported(self, body: str) -> bool:
        """Tem ao menos uma camada comum (não 'oversize') para esse tipo de corpo?"""
        return any(body in l["paths"] and not l["custom"] and not l["mask"] for l in self.layers)

    # --- cores ---------------------------------------------------------------------------
    def slots(self) -> list[dict]:
        """Lista de campos de cor: [{key, label, material, base, source, palettes}]."""
        r = self.recolors
        if not r:
            return []
        if "material" in r:
            return [{"key": "color_1", "label": "Cor", "material": r["material"], "base": r.get("base"),
                     "source": r.get("source"), "palettes": r.get("palettes") or ["ulpc"], "shared": None}]
        out = []
        for k in sorted(k for k in r if k.startswith("color_")):
            s = r[k]
            out.append({"key": k, "label": s.get("label") or k, "material": s["material"],
                        "base": s.get("base"), "source": s.get("source"),
                        "palettes": s.get("palettes") or ["ulpc"], "shared": s.get("type_name")})
        return out


class Catalog:
    def __init__(self, root: str):
        self.root = root
        self.items: dict[str, Item] = {}
        self._pal: dict[str, dict] = {}
        self._meta: dict[str, dict] = {}
        base = os.path.join(root, "sheet_definitions")
        for dp, _dn, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".json") or fn.startswith("meta_"):
                    continue
                full = os.path.join(dp, fn)
                try:
                    with open(full, encoding="utf-8") as fh:
                        d = json.load(fh)
                except (OSError, ValueError):
                    continue
                if not isinstance(d, dict) or "type_name" not in d:
                    continue
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                it = Item(fn[:-5], d, rel)
                if it.layers:
                    self.items[it.id] = it

    # --- paletas ---------------------------------------------------------------------------
    def meta(self, material: str) -> dict:
        if material not in self._meta:
            p = os.path.join(self.root, "palette_definitions", material, f"meta_{material}.json")
            try:
                with open(p, encoding="utf-8") as fh:
                    self._meta[material] = json.load(fh)
            except (OSError, ValueError):
                self._meta[material] = {}
        return self._meta[material]

    def palette(self, material: str, version: str) -> dict[str, list[str]]:
        key = f"{material}/{version}"
        if key not in self._pal:
            if "." in version:
                folder, ver = version.split(".", 1)
                p = os.path.join(self.root, "palette_definitions", folder, f"{folder}_{ver}.json")
            else:
                p = os.path.join(self.root, "palette_definitions", material, f"{material}_{version}.json")
            try:
                with open(p, encoding="utf-8") as fh:
                    self._pal[key] = json.load(fh)
            except (OSError, ValueError):
                self._pal[key] = {}
        return self._pal[key]

    def color_names(self, slot: dict) -> list[str]:
        names: list[str] = []
        for v in slot["palettes"]:
            for n in self.palette(slot["material"], v):
                if n not in names:
                    names.append(n)
        return names

    def target_colors(self, slot: dict, name: str) -> list[str] | None:
        for v in slot["palettes"]:
            pal = self.palette(slot["material"], v)
            if name in pal:
                return pal[name]
        return None

    def source_colors(self, slot: dict) -> list[str] | None:
        if slot.get("source"):
            return slot["source"]
        meta = self.meta(slot["material"])
        base = slot.get("base") or meta.get("base")
        pal = self.palette(slot["material"], meta.get("default", "ulpc"))
        return pal.get(base)

    # --- listagem para a interface -----------------------------------------------------------
    def listing(self, body: str) -> list[dict]:
        out = []
        for it in sorted(self.items.values(), key=lambda i: (i.group, i.type_name, i.sub, i.name.lower())):
            if not it.supported(body):
                continue
            out.append({
                "id": it.id, "name": it.name, "type": it.type_name, "group": it.group, "sub": it.sub,
                "variants": it.variants, "required": it.required_tags, "tags": it.tags,
                "match_body": it.match_body_color,
                "slots": [{"key": s["key"], "label": s["label"], "shared": s["shared"], "material": s["material"],
                           "colors": self.color_names(s),
                           "preview": {n: (self.target_colors(s, n) or ["#888"])[-2] for n in self.color_names(s)}}
                          for s in it.slots()],
            })
        return out


@lru_cache(maxsize=2)
def load(root: str) -> Catalog:
    return Catalog(root)
