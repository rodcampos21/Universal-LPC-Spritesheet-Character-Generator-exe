"""Analisador de quadros: recorta cada quadro sem perder a posição, para não haver 'tremida' na animação.

Dois modos:
- compact: cada quadro é recortado no menor retângulo possível e empacotado; o .tres do Godot usa a 'margin' do
  AtlasTexture para devolver o quadro ao tamanho/posição original (sem ajustes no jogo).
- fixed: todos os quadros (de todas as animações, inclusive as 'oversize') viram a MESMA caixa, centrada no
  centro original; basta centralizar o sprite.
"""
from __future__ import annotations

import json
import os

from PIL import Image

from .constants import ANIMS, CYCLES, DIRECTIONS, FPS, FRAME
from .export import godot_res_path, slug, unique_dir
from .render import CUSTOM, custom_names, render_custom, render_sheet


class AnimData:
    def __init__(self, name: str, fs: int, dirs: list[str], frames: list[list[Image.Image]], cycle=None):
        self.name, self.fs, self.dirs, self.frames, self.cycle = name, fs, dirs, frames, cycle

    @property
    def ncols(self) -> int:
        return max(len(r) for r in self.frames)


def _trim_tail(row: list[Image.Image]) -> list[Image.Image]:
    n = len(row)
    while n > 1 and row[n - 1].getchannel("A").getbbox() is None:
        n -= 1
    return row[:n]


def from_standard_sheet(sheet: Image.Image) -> list[AnimData]:
    out = []
    for name, (row, nrows, nframes) in ANIMS.items():
        if not sheet.crop((0, row * FRAME, nframes * FRAME, (row + nrows) * FRAME)).getbbox():
            continue
        dirs = DIRECTIONS if nrows == 4 else ["all"]
        frames = []
        for r in range(nrows):
            frames.append(_trim_tail([sheet.crop((c * FRAME, (row + r) * FRAME, (c + 1) * FRAME, (row + r + 1) * FRAME))
                                      for c in range(nframes)]))
        cols = max(len(f) for f in frames)
        frames = [f + [Image.new("RGBA", (FRAME, FRAME))] * (cols - len(f)) for f in frames]
        out.append(AnimData(name, FRAME, dirs, frames, CYCLES.get(name)))
    return out


def from_custom_sheet(name: str, img: Image.Image, fs: int) -> AnimData:
    rows = img.height // fs
    cols = img.width // fs
    dirs = DIRECTIONS if rows == 4 else [f"linha{i + 1}" for i in range(rows)]
    frames = [_trim_tail([img.crop((c * fs, r * fs, (c + 1) * fs, (r + 1) * fs)) for c in range(cols)])
              for r in range(rows)]
    cols = max(len(f) for f in frames)
    frames = [f + [Image.new("RGBA", (fs, fs))] * (cols - len(f)) for f in frames]
    return AnimData(name, fs, dirs, frames, list(range(cols)))


def _split_extra(h: int, img: Image.Image) -> list[int] | None:
    """Folha do gerador com áreas extras empilhadas abaixo dos 3456 px: descobre o tamanho de cada bloco."""
    sizes = (192, 128, 64)

    def walk(y, acc):
        if y == img.height:
            return acc
        for fs in sizes:
            if y + 4 * fs <= img.height:
                if not img.crop((0, y, img.width, y + 4 * fs)).getbbox():
                    continue
                r = walk(y + 4 * fs, acc + [fs])
                if r:
                    return r
        return None
    return walk(3456, [])


def from_png(img: Image.Image, frame_size: int = 0, name: str = "animacao") -> list[AnimData]:
    img = img.convert("RGBA")
    if img.width == 832 and img.height >= 3456:
        anims = from_standard_sheet(img.crop((0, 0, 832, 3456)))
        if img.height > 3456:
            blocks = _split_extra(img.height, img)
            if blocks is None:
                raise ValueError("Não consegui separar a área extra (animações grandes) dessa folha.")
            y = 3456
            for i, fs in enumerate(blocks, start=1):
                anims.append(from_custom_sheet(f"extra{i}_{fs}px", img.crop((0, y, img.width, y + 4 * fs)), fs))
                y += 4 * fs
        return anims
    fs = frame_size or (img.height // 4 if img.height // 4 in (64, 128, 192) and img.height % 4 == 0 else FRAME)
    if img.width % fs or img.height % fs:
        raise ValueError(f"O tamanho {img.width}×{img.height} não é múltiplo de {fs}. Informe o tamanho do quadro.")
    return [from_custom_sheet(name, img, fs)]


def _bbox(im: Image.Image):
    return im.getchannel("A").getbbox()


def analyze(anims: list[AnimData], mode: str = "compact") -> dict:
    """Mede tudo. Devolve dados prontos para exportar."""
    info = {}
    gx = gy = 0.0                                              # meia-caixa global (relativa ao centro)
    for a in anims:
        boxes = [[_bbox(f) for f in row] for row in a.frames]
        flat = [b for r in boxes for b in r if b]
        tw = max((b[2] - b[0] for b in flat), default=1)
        th = max((b[3] - b[1] for b in flat), default=1)
        info[a.name] = {"boxes": boxes, "tw": tw, "th": th}
        for b in flat:
            c = a.fs / 2
            gx = max(gx, abs(b[0] - c), abs(b[2] - c))
            gy = max(gy, abs(b[1] - c), abs(b[3] - c))
    return {"anims": info, "half": (int(gx + 0.999), int(gy + 0.999)), "mode": mode}


def _pack(a: AnimData, meas: dict, mode: str, half) -> tuple[Image.Image, dict]:
    """Monta a folha empacotada da animação e devolve (imagem, dados por quadro)."""
    boxes = meas["boxes"]
    rows, cols = len(a.frames), a.ncols
    if mode == "fixed":
        cw, ch = half[0] * 2, half[1] * 2
    else:
        cw, ch = meas["tw"], meas["th"]
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    data = {}
    c0 = a.fs / 2
    anchor = (a.fs - FRAME) // 2          # canto da célula padrão 64×64 dentro do quadro
    for r, row in enumerate(a.frames):
        data[a.dirs[r]] = []
        for c, fr in enumerate(row):
            b = boxes[r][c]
            if mode == "fixed":
                x0, y0 = int(c0 - half[0]), int(c0 - half[1])
                piece = Image.new("RGBA", (cw, ch))
                piece.paste(fr, (-x0, -y0))
                sheet.paste(piece, (c * cw, r * ch))
                data[a.dirs[r]].append({"bbox": list(b) if b else None, "region": [c * cw, r * ch, cw, ch],
                                        "offset": [x0 - anchor, y0 - anchor]})
            else:
                if b is None:
                    data[a.dirs[r]].append({"bbox": None, "region": [c * cw, r * ch, 1, 1],
                                            "margin": [0, 0, a.fs - 1, a.fs - 1], "offset": [0, 0]})
                    continue
                w, h = b[2] - b[0], b[3] - b[1]
                sheet.paste(fr.crop(b), (c * cw, r * ch))
                data[a.dirs[r]].append({"bbox": list(b), "region": [c * cw, r * ch, w, h],
                                        "margin": [b[0], b[1], a.fs - w, a.fs - h],
                                        "offset": [b[0] - anchor, b[1] - anchor]})
    return sheet, data


def tres(stem_res: dict, anims: list[AnimData], packed: dict, mode: str) -> str:
    ext, subs, blocks = [], [], []
    n = 0
    for k, a in enumerate(anims, start=1):
        ext.append('[ext_resource type="Texture2D" path="%s" id="%d"]' % (stem_res[a.name], k))
        for d in a.dirs:
            fr = []
            cyc = a.cycle or list(range(a.ncols))
            for idx in cyc:
                if idx >= a.ncols:
                    continue
                f = packed[a.name][d][idx]
                n += 1
                x, y, w, h = f["region"]
                s = (f'[sub_resource type="AtlasTexture" id="AtlasTexture_{n}"]\natlas = ExtResource("{k}")\n'
                     f'region = Rect2({x}, {y}, {w}, {h})\n')
                if mode == "compact":
                    m = f["margin"]
                    s += f'margin = Rect2({m[0]}, {m[1]}, {m[2]}, {m[3]})\n'
                subs.append(s)
                fr.append('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % n)
            nm = f"{a.name}_{d}" if d != "all" else a.name
            loop = "false" if a.name in ("hurt", "slash", "thrust", "spellcast", "shoot", "backslash", "halfslash") \
                or a.name in CUSTOM else "true"
            blocks.append('{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
                          % (", ".join(fr), loop, nm, float(FPS.get(a.name, 10 if a.name in CUSTOM else 8))))
    return ('[gd_resource type="SpriteFrames" load_steps=%d format=3]\n\n%s\n\n%s\n[resource]\nanimations = [%s]\n'
            % (len(subs) + 1 + len(ext), "\n".join(ext), "\n".join(subs), ", ".join(blocks)))


def export_analysis(anims: list[AnimData], out_root: str, name: str, mode: str = "compact",
                    loose: bool = False, source: str = "") -> dict:
    meas = analyze(anims, mode)
    base = slug(name)
    folder = unique_dir(out_root, base + "_frames")
    os.makedirs(folder)
    packed, paths_res, report, jdata = {}, {}, [], {}
    for a in anims:
        m = meas["anims"][a.name]
        sheet, data = _pack(a, m, mode, meas["half"])
        p = os.path.join(folder, f"{base}_{a.name}.png")
        sheet.save(p)
        packed[a.name] = data
        paths_res[a.name] = godot_res_path(p)
        cw, ch = (meas["half"][0] * 2, meas["half"][1] * 2) if mode == "fixed" else (m["tw"], m["th"])
        orig = a.ncols * a.fs * len(a.frames) * a.fs
        new = sheet.width * sheet.height
        report.append({"anim": a.name, "dirs": len(a.dirs), "frames": a.ncols, "original": a.fs,
                       "cell": [cw, ch], "saved_pct": round(100 * (1 - new / orig)) if orig else 0})
        jdata[a.name] = {"original_frame": a.fs, "cell": [cw, ch], "file": os.path.basename(p), "dirs": data}
        if loose:
            d = os.path.join(folder, "soltos", a.name)
            os.makedirs(d, exist_ok=True)
            for r, row in enumerate(a.frames):
                for c, fr in enumerate(row):
                    b = m["boxes"][r][c]
                    if mode == "fixed":
                        f = data[a.dirs[r]][c]["region"]
                        im = sheet.crop((f[0], f[1], f[0] + f[2], f[1] + f[3]))
                    else:
                        im = fr.crop(b) if b else Image.new("RGBA", (1, 1))
                    im.save(os.path.join(d, f"{a.dirs[r]}_{c + 1:02d}.png"))
    with open(os.path.join(folder, f"{base}_analise.json"), "w", encoding="utf-8") as fh:
        json.dump({"mode": mode, "source": source, "global_half_box": list(meas["half"]), "animations": jdata},
                  fh, ensure_ascii=False, indent=1)
    compat = []
    for a in anims:
        for d in a.dirs:
            compat.append({"name": a.name, "dir": d, "image": os.path.basename(jdata[a.name]["file"]),
                           "frame_time_ms": int(1000 / FPS.get(a.name, 10 if a.name in CUSTOM else 8)),
                           "frames": [{"rect": dict(zip("xywh", f["region"])),
                                       "offset": {"x": f["offset"][0], "y": f["offset"][1]}}
                                      for f in packed[a.name][d]]})
    with open(os.path.join(folder, f"{base}_lpcanalyzer.json"), "w", encoding="utf-8") as fh:
        json.dump({"animations": compat}, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(folder, f"{base}_frames.tres"), "w", encoding="utf-8") as fh:
        fh.write(tres(paths_res, anims, packed, mode))
    return {"folder": folder, "report": report, "mode": mode}


def analyze_character(cat, character: dict, out_root: str, name: str, mode="compact", loose=False) -> dict:
    sheet, _w = render_sheet(cat, character)
    anims = from_standard_sheet(sheet)
    for cname in custom_names(cat, character):
        cs = render_custom(cat, character, cname)
        if cs.getbbox():
            anims.append(from_custom_sheet(cname, cs, CUSTOM[cname]["frameSize"]))
    return export_analysis(anims, out_root, name, mode, loose, "personagem")


def analyze_folder(src_dir: str, out_root: str, mode="compact", loose=False, frame_size=0) -> dict:
    """Analisa todos os PNG de uma pasta (não recursivo)."""
    pngs = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".png"))
    if not pngs:
        raise ValueError("Não há PNG nessa pasta.")
    results, errors = [], []
    for f in pngs:
        try:
            im = Image.open(os.path.join(src_dir, f))
            im.load()
            anims = from_png(im, frame_size, slug(os.path.splitext(f)[0]))
            if not anims:
                errors.append(f"{f}: sem quadros desenhados")
                continue
            r = export_analysis(anims, out_root, os.path.splitext(f)[0], mode, loose, f)
            results.append({"file": f, "folder": r["folder"], "animations": len(anims)})
        except (ValueError, OSError) as e:
            errors.append(f"{f}: {e}")
    return {"results": results, "errors": errors, "folder": out_root}
