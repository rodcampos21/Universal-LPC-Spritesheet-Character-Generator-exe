"""Servidor local (127.0.0.1) + API usada pela interface."""
from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import analyze, assets, catalog, export, paths, randomize, render, uninstall
from .constants import ANIM_PT, ANIMS, BODY_PT, BODY_TYPES, CYCLES, DIR_PT, FPS
from .jobs import JobManager

if getattr(sys, "frozen", False):
    WEB = os.path.join(sys._MEIPASS, "lpcgen", "web")          # type: ignore[attr-defined]
else:
    WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MAX_BODY = 40 * 1024 * 1024


class AppError(Exception):
    pass


class App:
    def __init__(self, art_root: str | None = None):
        self.jobs = JobManager()
        self.stop = threading.Event()
        self.last_ping = 0.0
        self.lock = threading.Lock()
        self.art_root = art_root

    def root(self) -> str:
        return self.art_root or paths.art_dir()

    def cat(self) -> catalog.Catalog:
        if not assets.installed(self.root()):
            raise AppError("A arte ainda não foi baixada.")
        return catalog.load(self.root())

    def status(self) -> dict:
        return {"art": assets.installed(self.root()), "output_dir": paths.output_dir(), "art_dir": self.root(),
                "bodies": [{"id": b, "name": BODY_PT[b]} for b in BODY_TYPES],
                "anims": [{"id": a, "name": ANIM_PT[a], "row": ANIMS[a][0], "rows": ANIMS[a][1], "frames": ANIMS[a][2],
                          "cycle": CYCLES[a], "fps": FPS.get(a, 8)} for a in ANIMS],
                "dirs": DIR_PT}

    def set_art_dir(self, chosen: str, move: bool):
        """Muda o local da arte. Se já estiver baixada e move=True, move a pasta (tarefa em segundo plano)."""
        new = paths.art_dir_for(chosen)
        old = self.root()
        if os.path.abspath(new) == os.path.abspath(old):
            return {"art_dir": old}
        if os.path.isdir(new) and os.listdir(new) and not assets.installed(new):
            raise AppError(f"A pasta “{new}” já existe e tem outros arquivos. Escolha outra.")
        try:
            os.makedirs(os.path.dirname(new), exist_ok=True)
            probe = os.path.join(os.path.dirname(new), ".teste")
            with open(probe, "w") as fh:
                fh.write("x")
            os.remove(probe)
        except OSError as e:
            raise AppError(f"Não consigo usar “{chosen}”: {e.strerror or e}") from e
        if move and assets.installed(old) and not assets.installed(new):
            def work(progress, cancel):
                progress(0.1, "Movendo a arte…")
                shutil.move(old, new)
                paths.save_config(art_dir=new)
                self.art_root = None if not self.art_root else new
                return {"art_dir": new}
            j = self.jobs.submit("moveart", work, "Movendo a arte…")
            return {"job": j.id, "art_dir": new}
        paths.save_config(art_dir=new)
        if self.art_root:
            self.art_root = new
        return {"art_dir": new, "installed": assets.installed(new)}

    def output(self, override=None) -> str:
        out = os.path.abspath(str(override or paths.output_dir()))
        try:
            os.makedirs(out, exist_ok=True)
            probe = os.path.join(out, ".teste")
            with open(probe, "w") as fh:
                fh.write("x")
            os.remove(probe)
        except OSError as e:
            raise AppError(f"Não consigo salvar em “{out}”: {e.strerror or e}") from e
        return out

    # --- operações -------------------------------------------------------------------------
    def preview(self, character: dict) -> dict:
        cat = self.cat()
        with self.lock:
            sheet, warns = render.render_sheet(cat, character)
        buf = io.BytesIO()
        sheet.save(buf, "PNG")
        customs = {}
        with self.lock:
            for name in render.custom_names(cat, character):
                cs = render.render_custom(cat, character, name)
                if not cs.getbbox():
                    continue
                cb = io.BytesIO()
                cs.save(cb, "PNG")
                fs = render.CUSTOM[name]["frameSize"]
                customs[name] = {"png": "data:image/png;base64," + base64.b64encode(cb.getvalue()).decode(),
                                 "frameSize": fs, "cols": cs.width // fs}
        return {"png": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
                "warnings": warns, "animations": export.used_anims(sheet), "custom": customs}

    def save(self, character, name, opts, out=None) -> dict:
        cat = self.cat()
        root = self.output(out)
        with self.lock:
            return export.save_character(cat, character, root, name, opts)

    def analyze_character(self, b: dict) -> dict:
        cat = self.cat()
        root = self.output(b.get("output_dir"))
        mode = "fixed" if b.get("mode") == "fixed" else "compact"
        with self.lock:
            return analyze.analyze_character(cat, b.get("character") or {}, root, str(b.get("name") or "personagem"),
                                             mode, bool(b.get("loose")))

    def analyze_png(self, b: dict) -> dict:
        from PIL import Image
        root = self.output(b.get("output_dir"))
        mode = "fixed" if b.get("mode") == "fixed" else "compact"
        try:
            raw = base64.b64decode(str(b.get("png", "")).split(",", 1)[-1])
            im = Image.open(io.BytesIO(raw))
            im.load()
        except Exception as e:                                           # noqa: BLE001
            raise AppError("Não consegui abrir essa imagem (use PNG).") from e
        try:
            anims = analyze.from_png(im, int(b.get("frame_size") or 0), export.slug(str(b.get("name") or "animacao")))
        except ValueError as e:
            raise AppError(str(e)) from e
        if not anims:
            raise AppError("Não encontrei nenhum quadro desenhado nessa imagem.")
        return analyze.export_analysis(anims, root, str(b.get("name") or "animacao"), mode, bool(b.get("loose")),
                                       "png")

    def batch(self, b: dict, progress, cancel) -> dict:
        cat = self.cat()
        root = self.output(b.get("output_dir"))
        n = max(1, min(500, int(b.get("count") or 10)))
        prefix = export.slug(str(b.get("prefix") or "npc"))
        seed0 = int(b.get("seed") or int(time.time()) % 100000)
        body = b.get("body") if b.get("body") in BODY_TYPES else None
        folder = export.unique_dir(root, f"{prefix}_lote")
        os.makedirs(folder)
        opts = {"per_anim": bool(b.get("per_anim", False)), "gifs": bool(b.get("gifs", False)),
                "godot": bool(b.get("godot", True)), "flat": True}
        done = []
        for i in range(n):
            if cancel.is_set():
                break
            ch = randomize.random_character(cat, seed=seed0 + i, body=body)
            with self.lock:
                r = export.save_character(cat, ch, folder, f"{prefix}_{i + 1:03d}", opts)
            done.append(r["sheet"])
            progress((i + 1) / n, f"Gerando {i + 1} de {n}…")
        return {"folder": folder, "count": len(done)}


def open_folder(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)                                  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def make_handler(app: App, port_getter):
    class H(BaseHTTPRequestHandler):
        server_version = "LpcGerador"

        def log_message(self, *a):
            pass

        def _host_ok(self):
            return (self.headers.get("Host") or "").lower() in (f"127.0.0.1:{port_getter()}", f"localhost:{port_getter()}")

        def _send(self, data: bytes, ctype: str, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj, code=200):
            self._send(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

        def _err(self, msg, code=400):
            self._json({"error": msg}, code)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise AppError("Pedido grande demais.")
            try:
                d = json.loads((self.rfile.read(n) if n else b"{}").decode() or "{}")
            except ValueError as e:
                raise AppError("Pedido inválido.") from e
            return d if isinstance(d, dict) else {}

        def do_GET(self):
            if not self._host_ok():
                return self._err("Host não permitido.", 403)
            u = urlparse(self.path)
            try:
                self._get(u.path, parse_qs(u.query))
            except AppError as e:
                self._err(str(e))
            except Exception as e:                                       # noqa: BLE001
                self._err(f"Algo deu errado: {e}", 500)

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-App") != "1":
                return self._err("Pedido não permitido.", 403)
            try:
                self._post(urlparse(self.path).path, self._body())
            except AppError as e:
                self._err(str(e))
            except Exception as e:                                       # noqa: BLE001
                self._err(f"Algo deu errado: {e}", 500)

        def _get(self, path, q):
            if path in ("/", "/index.html"):
                with open(os.path.join(WEB, "index.html"), "rb") as fh:
                    return self._send(fh.read(), "text/html; charset=utf-8")
            m = re.fullmatch(r"/static/([\w\-.]+)", path)
            if m and os.path.isfile(os.path.join(WEB, m.group(1))):
                with open(os.path.join(WEB, m.group(1)), "rb") as fh:
                    return self._send(fh.read(), mimetypes.guess_type(m.group(1))[0] or "application/octet-stream")
            if path == "/api/status":
                return self._json(app.status())
            if path == "/api/catalog":
                body = q.get("body", ["male"])[0]
                if body not in BODY_TYPES:
                    raise AppError("Tipo de corpo inválido.")
                return self._json({"items": app.cat().listing(body)})
            if path == "/api/settings":
                return self._json(uninstall.scan())
            m = re.fullmatch(r"/api/jobs/([0-9a-f]+)", path)
            if m:
                j = app.jobs.get(m.group(1))
                return self._json(j.view()) if j else self._err("Tarefa não encontrada.", 404)
            return self._err("Não encontrado.", 404)

        def _post(self, path, b):
            if path == "/api/ping":
                app.last_ping = time.time()
                return self._json({"ok": True})
            if path == "/api/quit":
                self._json({"ok": True})
                app.stop.set()
                return
            if path == "/api/pickfolder":
                try:
                    return self._json({"path": uninstall.pick_folder(
                        str(b.get("initial") or paths.output_dir()),
                        str(b.get("title") or "Onde salvar as sprite sheets?"))})
                except RuntimeError as e:
                    raise AppError(str(e)) from e
            if path == "/api/config":
                out = str(b.get("output_dir") or "").strip()
                if not out:
                    raise AppError("Escolha uma pasta.")
                out = app.output(out)
                paths.save_config(output_dir=out)
                return self._json({"output_dir": out})
            if path == "/api/artdir":
                chosen = str(b.get("path") or "").strip()
                if not chosen:
                    raise AppError("Escolha uma pasta.")
                return self._json(app.set_art_dir(chosen, bool(b.get("move", True))))
            if path == "/api/openfolder":
                p = str(b.get("path") or paths.output_dir())
                if not os.path.isdir(p):
                    raise AppError("Essa pasta não existe ainda.")
                open_folder(p)
                return self._json({"ok": True})
            if path == "/api/download":
                if assets.installed(app.root()):
                    return self._json({"ok": True})
                j = app.jobs.submit("download", lambda prog, cancel: assets.download(prog, cancel, root=app.root()),
                                    "Baixando a arte…")
                return self._json({"job": j.id})
            m = re.fullmatch(r"/api/jobs/([0-9a-f]+)/cancel", path)
            if m:
                j = app.jobs.get(m.group(1))
                if j:
                    j.cancel.set()
                return self._json({"ok": True})
            if path == "/api/preview":
                return self._json(app.preview(b.get("character") or {}))
            if path == "/api/random":
                body = b.get("body") if b.get("body") in BODY_TYPES else None
                return self._json(randomize.random_character(app.cat(), body=body, seed=b.get("seed")))
            if path == "/api/default":
                body = b.get("body") if b.get("body") in BODY_TYPES else "male"
                return self._json(randomize.default_character(app.cat(), body))
            if path == "/api/save":
                r = app.save(b.get("character") or {}, str(b.get("name") or "personagem"),
                             b.get("options") or {}, b.get("output_dir"))
                return self._json(r)
            if path == "/api/analyze":
                return self._json(app.analyze_character(b))
            if path == "/api/analyze_png":
                return self._json(app.analyze_png(b))
            if path == "/api/batch":
                j = app.jobs.submit("batch", lambda prog, cancel: app.batch(b, prog, cancel), "Gerando…")
                return self._json({"job": j.id})
            if path == "/api/uninstall":
                return self._json(uninstall.run_uninstall())
            return self._err("Não encontrado.", 404)

    return H


def start(app: App, port: int = 0):
    holder = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, lambda: holder["port"]))
    holder["port"] = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, holder["port"]
