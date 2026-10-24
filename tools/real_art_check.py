"""Baixa a arte de verdade e confere que o app gera personagens (usado no CI)."""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lpcgen import assets, catalog, export, randomize                    # noqa: E402

root = os.path.join(tempfile.mkdtemp(), "arte")
last = [0]


def prog(f, msg=None):
    if int(f * 20) != last[0]:
        last[0] = int(f * 20)
        print(f"{f:.0%} {msg or ''}", flush=True)


assets.download(prog, threading.Event(), root=root)
assert assets.installed(root)
cat = catalog.load(root)
print("itens:", len(cat.items))
assert len(cat.items) > 500
out = tempfile.mkdtemp()
for body in ("male", "female", "teen", "child", "muscular", "pregnant"):
    for seed in range(4):
        ch = randomize.random_character(cat, seed=seed, body=body)
        r = export.save_character(cat, ch, out, f"{body}{seed}", {"gifs": False})
        from PIL import Image
        assert Image.open(r["sheet"]).getbbox(), (body, seed)
        assert "walk" in r["animations"], (body, seed, r["animations"])
# armas com golpe grande (camadas "oversize") precisam sair numa folha extra
ch = randomize.random_character(cat, seed=1, body="male")
ch["selections"]["weapon"] = {"itemId": "weapon_blunt_mace", "variant": "mace"}
r = export.save_character(cat, ch, out, "maca", {"gifs": True})
assert "slash_oversize" in r["animations"], r["animations"]
extra = [f for f in r["files"] if f.endswith("maca_slash_oversize.png")]
assert extra and Image.open(extra[0]).getbbox() and Image.open(extra[0]).size == (1152, 768)
assert "slash_oversize_down" in open(os.path.join(r["folder"], "maca.tres"), encoding="utf-8").read()
print("ok")
