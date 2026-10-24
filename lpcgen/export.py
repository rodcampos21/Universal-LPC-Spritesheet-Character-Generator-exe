"""Salva o personagem na pasta escolhida: folha completa, animações, GIFs, créditos, .tres do Godot."""
from __future__ import annotations

import csv
import io
import json
import os
import re

from PIL import Image

from .catalog import Catalog
from .constants import ANIMS, CYCLES, DIRECTIONS, FPS, FRAME
from . import celshade
from .render import CUSTOM, custom_names, render_custom, render_sheet, resolve


def slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE).strip("_")
    return s or "personagem"


def unique_dir(parent: str, name: str) -> str:
    p = os.path.join(parent, name)
    n = 2
    while os.path.exists(p):
        p = os.path.join(parent, f"{name}_{n}")
        n += 1
    return p


def used_anims(sheet: Image.Image) -> list[str]:
    """Só as animações que têm algum pixel desenhado."""
    out = []
    for name, (row, nrows, nframes) in ANIMS.items():
        box = (0, row * FRAME, nframes * FRAME, (row + nrows) * FRAME)
        if sheet.crop(box).getbbox():
            out.append(name)
    return out


def crop_anim(sheet: Image.Image, name: str) -> Image.Image:
    row, nrows, nframes = ANIMS[name]
    return sheet.crop((0, row * FRAME, nframes * FRAME, (row + nrows) * FRAME))


def frame(sheet: Image.Image, name: str, direction: str, idx: int) -> Image.Image:
    row, nrows, _n = ANIMS[name]
    r = row + (DIRECTIONS.index(direction) if nrows == 4 else 0)
    return sheet.crop((idx * FRAME, r * FRAME, (idx + 1) * FRAME, (r + 1) * FRAME))


def gif_bytes(sheet: Image.Image, name: str, scale: int = 3, directions=None, custom_fs: int = 0) -> bytes:
    if custom_fs:                                   # animação extra: 4 linhas de quadros grandes
        dirs = DIRECTIONS
        cycle = list(range(sheet.width // custom_fs))
        scale = max(1, scale - 1)
    else:
        nrows = ANIMS[name][1]
        dirs = directions or (DIRECTIONS if nrows == 4 else ["down"])
        cycle = CYCLES[name]
    fsz = custom_fs or FRAME
    frames = []
    for idx in cycle:
        strip = Image.new("RGBA", (fsz * len(dirs), fsz), (0, 0, 0, 0))
        for i, d in enumerate(dirs):
            if custom_fs:
                fr = sheet.crop((idx * fsz, i * fsz, (idx + 1) * fsz, (i + 1) * fsz))
            else:
                fr = frame(sheet, name, d, idx)
            strip.alpha_composite(fr, (i * fsz, 0))
        strip = strip.resize((strip.width * scale, strip.height * scale), Image.NEAREST)
        bg = Image.new("RGBA", strip.size, (58, 62, 74, 255))
        bg.alpha_composite(strip)
        frames.append(bg.convert("P", palette=Image.ADAPTIVE))
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], loop=0,
                   duration=int(1000 / (10 if custom_fs else FPS.get(name, 8))), disposal=2)
    return buf.getvalue()


def credits_rows(cat: Catalog, character: dict) -> list[dict]:
    pairs, _ = resolve(cat, character)
    rows, seen = [], set()
    for it, _s in pairs:
        for c in it.credits:
            key = (it.id, c.get("file"))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"item": it.name, "file": c.get("file", ""), "notes": c.get("notes", ""),
                         "authors": "; ".join(c.get("authors") or []),
                         "licenses": "; ".join(c.get("licenses") or []),
                         "urls": " ".join(c.get("urls") or [])})
    return rows


def credits_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["item", "file", "notes", "authors", "licenses", "urls"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def credits_txt(rows: list[dict]) -> str:
    out = ["CRÉDITOS (obrigatório manter ao usar estes sprites, mesmo em jogo privado)", ""]
    for r in rows:
        out.append(f"- {r['item']} [{r['file']}]\n  Autores: {r['authors']}\n  Licenças: {r['licenses']}\n  {r['urls']}")
    return "\n".join(out) + "\n"


def godot_res_path(png_path: str) -> str:
    """Se a pasta está dentro de um projeto Godot (project.godot), devolve res://caminho; senão res://nome.png."""
    d = os.path.dirname(os.path.abspath(png_path))
    cur = d
    while True:
        if os.path.isfile(os.path.join(cur, "project.godot")):
            rel = os.path.relpath(png_path, cur).replace(os.sep, "/")
            return "res://" + rel
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return "res://" + os.path.basename(png_path)


def spriteframes_tres(sheet_res: str, anims: list[str], customs=(), scale: int = 1) -> str:
    """customs: [(nome, caminho res://, tamanho do quadro, colunas)]"""
    subs, blocks = [], []
    n = 0
    ext = ['[ext_resource type="Texture2D" path="%s" id="1"]' % sheet_res]
    for k, (cname, cres, cfs, ccols) in enumerate(customs, start=2):
        ext.append('[ext_resource type="Texture2D" path="%s" id="%d"]' % (cres, k))
        cfs *= scale
        for di, d in enumerate(DIRECTIONS):
            fr = []
            for idx in range(ccols):
                n += 1
                subs.append(f'[sub_resource type="AtlasTexture" id="AtlasTexture_{n}"]\n'
                            f'atlas = ExtResource("{k}")\nregion = Rect2({idx * cfs}, {di * cfs}, {cfs}, {cfs})\n')
                fr.append('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % n)
            blocks.append('{\n"frames": [%s],\n"loop": false,\n"name": &"%s_%s",\n"speed": 10.0\n}'
                          % (", ".join(fr), cname, d))
    for name in anims:
        row, nrows, _nf = ANIMS[name]
        dirs = DIRECTIONS if nrows == 4 else [None]
        for d in dirs:
            fr = []
            for idx in CYCLES[name]:
                n += 1
                y = (row + (DIRECTIONS.index(d) if d else 0)) * FRAME * scale
                subs.append(f'[sub_resource type="AtlasTexture" id="AtlasTexture_{n}"]\n'
                            f'atlas = ExtResource("1")\nregion = Rect2({idx * FRAME * scale}, {y}, {FRAME * scale}, {FRAME * scale})\n')
                fr.append('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % n)
            loop = "false" if name in ("hurt", "slash", "thrust", "spellcast", "shoot", "backslash", "halfslash") else "true"
            nm = f"{name}_{d}" if d else name
            blocks.append('{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
                          % (", ".join(fr), loop, nm, float(FPS.get(name, 8))))
    return ('[gd_resource type="SpriteFrames" load_steps=%d format=3]\n\n'
            '%s\n\n%s\n[resource]\nanimations = [%s]\n'
            % (len(subs) + 1 + len(ext), "\n".join(ext), "\n".join(subs), ", ".join(blocks)))


def save_character(cat: Catalog, character: dict, out_root: str, name: str, opts: dict | None = None) -> dict:
    """Salva tudo em <out_root>/<nome>/ . Retorna caminhos."""
    opts = {"per_anim": True, "gifs": True, "godot": True, "flat": False, "hd": None, **(opts or {})}
    sheet, warns = render_sheet(cat, character)
    base = slug(name)
    folder = out_root if opts["flat"] else unique_dir(out_root, base)
    os.makedirs(folder, exist_ok=True)
    stem = base if opts["flat"] else base
    png = os.path.join(folder, stem + ".png")
    if opts["flat"] and os.path.exists(png):
        k = 2
        while os.path.exists(os.path.join(folder, f"{base}_{k}.png")):
            k += 1
        stem = f"{base}_{k}"
        png = os.path.join(folder, stem + ".png")
    sheet.save(png)
    anims = used_anims(sheet)
    files = [png]
    customs = []
    for cname in custom_names(cat, character):
        csheet = render_custom(cat, character, cname)
        if not csheet.getbbox():
            continue
        cp = os.path.join(folder, f"{stem}_{cname}.png")
        csheet.save(cp)
        files.append(cp)
        fs = CUSTOM[cname]["frameSize"]
        customs.append((cname, cp, fs, csheet.width // fs, csheet))
    if opts["per_anim"]:
        d = os.path.join(folder, "animacoes", stem) if opts["flat"] else os.path.join(folder, "animacoes")
        os.makedirs(d, exist_ok=True)
        for a in anims:
            p = os.path.join(d, f"{a}.png")
            crop_anim(sheet, a).save(p)
            files.append(p)
    if opts["gifs"]:
        d = os.path.join(folder, "previas", stem) if opts["flat"] else os.path.join(folder, "previas")
        os.makedirs(d, exist_ok=True)
        for a in anims:
            if a in ("walk", "idle", "run", "slash", "combat_idle", "hurt", "spellcast", "thrust"):
                p = os.path.join(d, f"{a}.gif")
                with open(p, "wb") as fh:
                    fh.write(gif_bytes(sheet, a))
                files.append(p)
    if opts["hd"]:                                   # versão HD cel shade (experimental)
        hp = celshade.clean(opts["hd"] if isinstance(opts["hd"], dict) else {})
        sc = hp["scale"]
        hd_png = os.path.join(folder, f"{stem}_hd.png")
        celshade.celshade_sheet(sheet, FRAME, hp).save(hd_png)
        files.append(hd_png)
        hd_customs = []
        for c in customs:
            cp_hd = os.path.join(folder, f"{stem}_{c[0]}_hd.png")
            celshade.celshade_sheet(c[4], c[2], hp).save(cp_hd)
            files.append(cp_hd)
            hd_customs.append((c[0], godot_res_path(cp_hd), c[2], c[3]))
        if opts["godot"]:
            tp = os.path.join(folder, stem + "_hd.tres")
            with open(tp, "w", encoding="utf-8") as fh:
                fh.write(spriteframes_tres(godot_res_path(hd_png), anims, hd_customs, sc))
            files.append(tp)
    if opts["gifs"]:
        d = os.path.join(folder, "previas", stem) if opts["flat"] else os.path.join(folder, "previas")
        os.makedirs(d, exist_ok=True)
        for c in customs:
            p = os.path.join(d, f"{c[0]}.gif")
            with open(p, "wb") as fh:
                fh.write(gif_bytes(c[4], c[0], custom_fs=c[2]))
            files.append(p)
    meta = os.path.join(folder, stem + ".json")
    with open(meta, "w", encoding="utf-8") as fh:
        json.dump({**character, "version": 2}, fh, ensure_ascii=False, indent=1)
    files.append(meta)
    rows = credits_rows(cat, character)
    cp = os.path.join(folder, stem + "_CREDITOS.csv" if opts["flat"] else "CREDITOS.csv")
    with open(cp, "w", encoding="utf-8", newline="") as fh:
        fh.write(credits_csv(rows))
    files.append(cp)
    if not opts["flat"]:
        tp = os.path.join(folder, "CREDITOS.txt")
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write(credits_txt(rows))
        files.append(tp)
    if opts["godot"]:
        tp = os.path.join(folder, stem + ".tres")
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write(spriteframes_tres(godot_res_path(png), anims,
                                       [(c[0], godot_res_path(c[1]), c[2], c[3]) for c in customs]))
        files.append(tp)
    return {"folder": folder, "sheet": png, "files": files, "warnings": warns, "animations": anims + [c[0] for c in customs]}
