"""Sorteio de personagens (para NPCs em lote)."""
from __future__ import annotations

import random

from .catalog import Catalog, Item
from .constants import BODY_TYPES
from .render import tag_ok

SKIN = {"light", "amber", "olive", "taupe", "bronze", "brown", "black", "ivory", "porcelain", "peach", "tan",
        "tawny", "honey", "coffee"}
HAIR = {"platinum", "gray", "blonde", "sandy", "strawberry", "ginger", "carrot", "redhead", "red", "light_brown",
        "chestnut", "dark_brown", "dark_gray", "black", "raven", "orange", "ash", "white"}
# (type_name, chance)
PLAN = [("body", 1.0), ("head", 1.0), ("expression", 1.0), ("eyebrows", 0.7),
        ("nose", 0.4), ("ears", 0.0), ("hair", 0.9), ("beard", 0.15), ("mustache", 0.08),
        ("clothes", 1.0), ("legs", 0.95), ("shoes", 0.9), ("jacket", 0.2), ("vest", 0.12),
        ("belt", 0.3), ("hat", 0.2), ("cape", 0.08), ("backpack", 0.08), ("necklace", 0.1),
        ("earrings", 0.1), ("gloves", 0.0), ("weapon", 0.1)]


def _pick_color(cat: Catalog, it: Item, rng: random.Random, body_sel: dict | None):
    sel: dict = {"itemId": it.id, "name": it.name}
    slots = it.slots()
    if slots:
        if it.match_body_color and body_sel:
            sel["recolor"] = body_sel.get("recolor")
        else:
            rc = {}
            for s in slots:
                names = cat.color_names(s)
                if s["material"] == "body":
                    names = [n for n in names if n in SKIN] or names
                elif s["material"] == "hair":
                    names = [n for n in names if n in HAIR] or names
                rc[s["key"]] = rng.choice(names)
            sel["recolor"] = rc["color_1"] if len(slots) == 1 else rc
        sel["variant"] = ""
    elif it.variants:
        sel["variant"] = rng.choice(it.variants)
    else:
        sel["variant"] = ""
    return sel


def default_head(cat: Catalog, body: str, rng=None) -> Item | None:
    heads = [i for i in cat.items.values() if i.type_name == "head" and i.supported(body)]
    if not heads:
        return None
    sex = "female" if body in ("female", "pregnant") else "male"
    exact = [i for i in heads if i.id == f"heads_human_{sex}"]
    pool = exact or sorted([i for i in heads if "human" in i.id], key=lambda i: len(i.id)) or heads
    return pool[0]


def random_character(cat: Catalog, seed: int | None = None, body: str | None = None, rng=None) -> dict:
    rng = rng or random.Random(seed)
    body = body or rng.choice(["male", "female", "male", "female", "teen", "muscular", "child"])
    sel: dict = {}
    chosen: list[Item] = []
    body_sel = None
    for tname, chance in PLAN:
        if rng.random() > chance:
            continue
        if tname in ("beard", "mustache") and body not in ("male", "muscular"):
            continue
        if tname == "head":
            it = default_head(cat, body, rng)
            pool = [it] if it else []
        else:
            pool = [i for i in cat.items.values() if i.type_name == tname and i.supported(body)
                    and (tname != "body" or i.id == "body")]
            pool = [i for i in pool if tag_ok(i, chosen + [i])]
        if not pool:
            continue
        it = rng.choice(sorted(pool, key=lambda i: i.id))
        s = _pick_color(cat, it, rng, body_sel)
        if tname == "body":
            body_sel = s
        sel[tname] = s
        chosen.append(it)
    shared = {}
    for it in chosen:
        for sl in it.slots():
            if sl.get("shared") and sl["shared"] not in shared:
                shared[sl["shared"]] = rng.choice(cat.color_names(sl))
    return {"version": 2, "bodyType": body, "selections": sel, "shared": shared}


def default_character(cat: Catalog, body: str = "male") -> dict:
    ch = random_character(cat, seed=7, body=body)
    return ch
