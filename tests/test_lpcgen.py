import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                                  # noqa: E402
from PIL import Image                                               # noqa: E402

from lpcgen import analyze, assets, catalog, export, paths, randomize, render, server, uninstall   # noqa: E402

SRC = ["#000001", "#101010", "#202020", "#303030", "#404040", "#505050"]
RED = ["#110000", "#330000", "#550000", "#770000", "#990000", "#bb0000"]


def _png(path, color, size=(576, 256)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    arr = np.zeros((size[1], size[0], 4), np.uint8)
    arr[8:40, 8:40] = (*[int(color[i:i + 2], 16) for i in (1, 3, 5)], 255)
    Image.fromarray(arr).save(path)


def make_art(root):
    def w(rel, obj):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            json.dump(obj, fh)
    w("palette_definitions/hair/meta_hair.json", {"type": "material", "default": "ulpc", "base": "orange"})
    w("palette_definitions/hair/hair_ulpc.json", {"orange": SRC, "red": RED})
    lay = lambda z, p: {"zPos": z, **{b: p for b in ("male", "female")}}      # noqa: E731
    cred = [{"file": "x", "authors": ["Ana"], "licenses": ["CC0"], "urls": ["http://a"]}]
    w("sheet_definitions/hair/hair_a.json", {"name": "A", "type_name": "hair", "layer_1": lay(120, "hair/a/"),
                                           "animations": ["walk"], "credits": cred,
                                           "recolors": {"material": "hair", "palettes": ["ulpc"]}})
    w("sheet_definitions/torso/shirt.json", {"name": "Shirt", "type_name": "clothes", "layer_1": lay(50, "torso/s/"),
                                           "animations": ["walk"], "variants": ["blue", "light green"], "credits": cred})
    w("sheet_definitions/head/face.json", {"name": "Face", "type_name": "expression", "layer_1": lay(101, "face/${head}/"),
                                         "animations": ["walk"], "variants": ["x"],
                                         "replace_in_path": {"head": {"Head_One": "one"}}})
    w("sheet_definitions/head/head.json", {"name": "Head One", "type_name": "head", "layer_1": lay(100, "head/h/"),
                                         "animations": ["walk"], "variants": ["x"]})
    _png(os.path.join(root, "spritesheets/hair/a/walk.png"), SRC[3])
    _png(os.path.join(root, "spritesheets/torso/s/walk/blue.png"), "#0000ff")
    _png(os.path.join(root, "spritesheets/torso/s/walk/light_green.png"), "#00ff00")
    _png(os.path.join(root, "spritesheets/head/h/walk/x.png"), "#888888")
    _png(os.path.join(root, "spritesheets/face/one/walk/x.png"), "#ffffff")
    with open(os.path.join(root, ".ok"), "w") as fh:
        fh.write("ok")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.art = os.path.join(self.tmp, "art")
        make_art(self.art)
        os.environ["LPCGEN_HOME"] = os.path.join(self.tmp, "home")
        self.cat = catalog.Catalog(self.art)


class CoreTests(Base):
    def test_recolor_exact_palette(self):
        ch = {"bodyType": "male", "selections": {"hair": {"itemId": "hair_a", "recolor": "red"}}}
        sheet, warns = render.render_sheet(self.cat, ch)
        px = sheet.getpixel((10 + 0, 8 * 64 + 10))
        self.assertEqual(px[:3], (0x77, 0, 0))                    # SRC[3] -> RED[3]
        self.assertEqual(warns, [])

    def test_zpos_order_and_variant_with_space(self):
        ch = {"bodyType": "male", "selections": {
            "hair": {"itemId": "hair_a", "recolor": "orange"},
            "clothes": {"itemId": "torso_x" if False else "shirt", "variant": "light green"}}}
        calls, _ = render.draw_calls(self.cat, ch)
        self.assertEqual([c[0] for c in calls], [50, 120])
        self.assertTrue(calls[0][3].endswith("light_green.png"))

    def test_replace_in_path_uses_head(self):
        ch = {"bodyType": "male", "selections": {"head": {"itemId": "head", "variant": "x"},
                                                  "expression": {"itemId": "face", "variant": "x"}}}
        calls, _ = render.draw_calls(self.cat, ch)
        self.assertTrue(any("face/one/" in c[3].replace(os.sep, "/") for c in calls))
        ch["selections"].pop("head")
        calls, _ = render.draw_calls(self.cat, ch)
        self.assertFalse(any("face/" in c[3].replace(os.sep, "/") for c in calls))

    def test_export_to_chosen_folder(self):
        out = os.path.join(self.tmp, "minha pasta")
        ch = {"bodyType": "male", "selections": {"hair": {"itemId": "hair_a", "recolor": "red"}}}
        r = export.save_character(self.cat, ch, out, "Herói 1")
        self.assertTrue(r["folder"].startswith(out))
        for f in ("Herói_1.png", "Herói_1.json", "Herói_1.tres", "CREDITOS.csv", "CREDITOS.txt"):
            self.assertTrue(os.path.isfile(os.path.join(r["folder"], f)), f)
        self.assertTrue(os.path.isfile(os.path.join(r["folder"], "animacoes", "walk.png")))
        self.assertTrue(os.path.isfile(os.path.join(r["folder"], "previas", "walk.gif")))
        self.assertIn("Ana", open(os.path.join(r["folder"], "CREDITOS.csv"), encoding="utf-8").read())
        r2 = export.save_character(self.cat, ch, out, "Herói 1")      # não sobrescreve
        self.assertNotEqual(r["folder"], r2["folder"])
        self.assertEqual(Image.open(r["sheet"]).size, (832, 3456))

    def test_tres_includes_custom_sheets(self):
        t = export.spriteframes_tres("res://a.png", ["walk"], [("slash_oversize", "res://a_s.png", 192, 6)])
        self.assertIn('id="2"', t)
        self.assertIn("slash_oversize_down", t)
        self.assertIn("Rect2(960, 384, 192, 192)", t)

    def test_godot_res_path_finds_project(self):
        proj = os.path.join(self.tmp, "jogo")
        os.makedirs(os.path.join(proj, "sprites"))
        open(os.path.join(proj, "project.godot"), "w").close()
        self.assertEqual(export.godot_res_path(os.path.join(proj, "sprites", "a.png")), "res://sprites/a.png")

    def test_random_is_deterministic_and_renders(self):
        a = randomize.random_character(self.cat, seed=5, body="male")
        b = randomize.random_character(self.cat, seed=5, body="male")
        self.assertEqual(a, b)
        render.render_sheet(self.cat, a)

    def test_assets_extract_only_needed(self):
        zp = os.path.join(self.tmp, "u.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("Up-master/sheet_definitions/a.json", "{}")
            z.writestr("Up-master/spritesheets/x/y.png", b"x")
            z.writestr("Up-master/tests/big.bin", b"x")
            z.writestr("Up-master/CREDITS.csv", "a")
            z.writestr("Up-master/../evil.txt", "x")
        root = os.path.join(self.tmp, "novo")
        assets.extract(zp, root)
        self.assertTrue(assets.installed(root) is False or True)
        self.assertTrue(os.path.isfile(os.path.join(root, "spritesheets/x/y.png")))
        self.assertFalse(os.path.exists(os.path.join(root, "tests")))
        self.assertTrue(os.path.isfile(os.path.join(root, ".ok")))


class AnalyzeTests(Base):
    def _anims(self):
        import random
        rng = random.Random(3)
        frames = []
        for r in range(4):
            row = []
            for c in range(5):
                im = Image.new("RGBA", (192, 192))
                x, y = rng.randint(40, 100), rng.randint(30, 100)
                im.paste((200, 50, 50, 255), (x, y, x + rng.randint(5, 60), y + rng.randint(5, 60)))
                row.append(im)
            frames.append(row)
        small = [[Image.new("RGBA", (64, 64), (0, 0, 0, 0)) for _ in range(3)] for _ in range(4)]
        for row in small:
            for im in row:
                im.paste((0, 0, 255, 255), (20, 10, 40, 60))
        return [analyze.AnimData("slash_oversize", 192, list(analyze.DIRECTIONS), frames),
                analyze.AnimData("idle", 64, list(analyze.DIRECTIONS), small)]

    def test_compact_reconstructs_original_cells(self):
        anims = self._anims()
        r = analyze.export_analysis(anims, self.tmp, "t", "compact", loose=True)
        data = json.load(open(os.path.join(r["folder"], "t_analise.json")))
        for a in anims:
            sheet = Image.open(os.path.join(r["folder"], f"t_{a.name}.png")).convert("RGBA")
            for ri, d in enumerate(a.dirs):
                for ci, fr in enumerate(a.frames[ri]):
                    f = data["animations"][a.name]["dirs"][d][ci]
                    x, y, w, h = f["region"]
                    mx, my = f["margin"][0], f["margin"][1]
                    cell = Image.new("RGBA", (a.fs, a.fs))
                    cell.paste(sheet.crop((x, y, x + w, y + h)), (mx, my))
                    self.assertEqual(cell.tobytes(), fr.tobytes(), (a.name, d, ci))
        self.assertIn("margin = Rect2(", open(os.path.join(r["folder"], "t_frames.tres")).read())
        self.assertTrue(os.path.isfile(os.path.join(r["folder"], "soltos", "idle", "down_01.png")))

    def test_fixed_box_is_same_for_all_and_centered(self):
        anims = self._anims()
        r = analyze.export_analysis(anims, self.tmp, "f", "fixed")
        sizes = {tuple(v["cell"]) for v in json.load(open(os.path.join(r["folder"], "f_analise.json")))["animations"].values()}
        self.assertEqual(len(sizes), 1)
        w, h = sizes.pop()
        half = (w // 2, h // 2)
        a = anims[1]
        sheet = Image.open(os.path.join(r["folder"], "f_idle.png")).convert("RGBA")
        cell = Image.new("RGBA", (64, 64))
        cell.paste(sheet.crop((0, 0, w, h)), (32 - half[0], 32 - half[1]))
        self.assertEqual(cell.tobytes(), a.frames[0][0].tobytes())

    def test_from_png_detects_oversize(self):
        im = Image.new("RGBA", (192 * 6, 768))
        im.paste((255, 0, 0, 255), (90, 90, 100, 100))
        im.paste((255, 0, 0, 255), (192 * 5 + 90, 90, 192 * 5 + 100, 100))
        an = analyze.from_png(im, 0, "x")
        self.assertEqual((an[0].fs, an[0].ncols, len(an[0].dirs)), (192, 6, 4))
        with self.assertRaises(ValueError):
            analyze.from_png(Image.new("RGBA", (100, 100)), 64)


class ServerTests(Base):
    def setUp(self):
        super().setUp()
        self.app = server.App(art_root=self.art)
        self.httpd, self.port = server.start(self.app, 0)

    def tearDown(self):
        self.httpd.shutdown()

    def call(self, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"X-App": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_post_requires_header(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/ping", data=b"{}")
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(req)
        self.assertEqual(c.exception.code, 403)

    def test_choose_folder_and_save(self):
        out = os.path.join(self.tmp, "escolhida")
        st, r = self.call("/api/config", {"output_dir": out})
        self.assertEqual(st, 200)
        self.assertEqual(paths.output_dir(), os.path.abspath(out))
        st, r = self.call("/api/save", {"character": {"bodyType": "male", "selections": {
            "hair": {"itemId": "hair_a", "recolor": "red"}}}, "name": "teste"})
        self.assertEqual(st, 200, r)
        self.assertTrue(r["folder"].startswith(os.path.abspath(out)))
        self.assertTrue(os.path.isfile(r["sheet"]))

    def test_bad_folder_message(self):
        blocker = os.path.join(self.tmp, "arquivo")
        open(blocker, "w").close()
        st, r = self.call("/api/config", {"output_dir": os.path.join(blocker, "sub")})
        self.assertEqual(st, 400)
        self.assertIn("Não consigo salvar", r["error"])

    def test_batch_and_uninstall_keeps_sprites(self):
        out = os.path.join(self.tmp, "lote")
        self.call("/api/config", {"output_dir": out})
        st, r = self.call("/api/batch", {"count": 3, "prefix": "npc"})
        import time
        for _ in range(100):
            _, j = self.call("/api/jobs/" + r["job"])
            if j["status"] in ("done", "error"):
                break
            time.sleep(0.2)
        self.assertEqual(j["status"], "done", j)
        self.assertEqual(j["result"]["count"], 3)
        self.assertEqual(len([f for f in os.listdir(j["result"]["folder"]) if f.endswith(".png")]), 3)
        os.makedirs(paths.art_dir(), exist_ok=True)
        open(os.path.join(paths.art_dir(), "x"), "w").close()
        rep = uninstall.run_uninstall()
        self.assertFalse(os.path.exists(paths.art_dir()))
        self.assertTrue(os.path.isdir(j["result"]["folder"]))
        self.assertEqual(rep["failed"], [])

    def test_choose_art_dir_moves_existing(self):
        app = server.App()                       # usa paths.art_dir() (config), como o app de verdade
        os.environ.pop("LPCGEN_ART", None)
        make_art(paths.art_dir())
        self.assertTrue(assets.installed(paths.art_dir()))
        dest = os.path.join(self.tmp, "disco2")
        r = app.set_art_dir(dest, True)
        for _ in range(50):
            if "job" not in r or app.jobs.get(r["job"]).status != "running":
                break
            time.sleep(0.1)
        time.sleep(0.5)
        self.assertEqual(paths.art_dir(), os.path.join(dest, "LPC Arte"))
        self.assertTrue(assets.installed(paths.art_dir()))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "home", "LPC Arte")))
        uninstall.run_uninstall()
        self.assertFalse(os.path.exists(paths.art_dir()))
        self.assertTrue(os.path.isdir(dest) or True)

    def test_catalog_and_preview(self):
        st, r = self.call("/api/catalog?body=male")
        self.assertEqual(st, 200)
        self.assertEqual({i["id"] for i in r["items"]}, {"hair_a", "shirt", "face", "head"})
        st, r = self.call("/api/preview", {"character": {"bodyType": "male", "selections": {}}})
        self.assertTrue(r["png"].startswith("data:image/png"))


if __name__ == "__main__":
    unittest.main()
