"""Baixa a arte do gerador LPC (GitHub) só na primeira vez; guarda só o que o app usa."""
from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
import zipfile

from . import paths
from .constants import UPSTREAM_ZIP

KEEP = ("sheet_definitions/", "palette_definitions/", "spritesheets/")
KEEP_FILES = ("CREDITS.csv", "LICENSE")


def installed(root: str | None = None) -> bool:
    root = root or paths.art_dir()
    return os.path.isdir(os.path.join(root, "sheet_definitions")) and \
        os.path.isdir(os.path.join(root, "spritesheets")) and \
        os.path.isfile(os.path.join(root, ".ok"))


def download(progress, cancel, url: str = UPSTREAM_ZIP, root: str | None = None) -> None:
    """Baixa o zip, extrai só as pastas necessárias. progress(frac, msg)."""
    root = root or paths.art_dir()
    os.makedirs(os.path.dirname(root), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".zip", dir=os.path.dirname(root))
    os.close(fd)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lpc-sprite-gerador"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                if cancel.is_set():
                    raise RuntimeError("cancelado")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                progress(0.6 * (got / total if total else min(0.95, got / 600e6)),
                         f"Baixando a arte… {got // (1 << 20)} MB")
        extract(tmp, root, lambda f: progress(0.6 + 0.4 * f, "Extraindo…"), cancel)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def extract(zip_path: str, root: str, progress=lambda f: None, cancel=None) -> None:
    stage = root + ".novo"
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        top = names[0].split("/")[0] + "/"
        wanted = []
        for n in names:
            rel = n[len(top):] if n.startswith(top) else n
            if not rel or rel.endswith("/"):
                continue
            if rel.startswith(KEEP) or rel in KEEP_FILES:
                wanted.append((n, rel))
        for i, (n, rel) in enumerate(wanted):
            if cancel is not None and cancel.is_set():
                raise RuntimeError("cancelado")
            dest = os.path.realpath(os.path.join(stage, rel))
            if not dest.startswith(os.path.realpath(stage) + os.sep):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(n) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if i % 500 == 0:
                progress(i / max(1, len(wanted)))
    with open(os.path.join(stage, ".ok"), "w") as fh:
        fh.write("ok")
    shutil.rmtree(root, ignore_errors=True)
    os.replace(stage, root)
