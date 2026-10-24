from __future__ import annotations

import os
import shutil

from . import paths


def _size(p: str) -> int:
    t = 0
    for b, _d, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(b, f))
            except OSError:
                pass
    return t


def scan() -> dict:
    items = []
    if os.path.isdir(paths.art_dir()):
        items.append({"id": "art", "label": "Arte baixada (sprites do LPC)", "bytes": _size(paths.art_dir())})
    if os.path.isfile(paths.config_path()):
        items.append({"id": "config", "label": "Configurações", "bytes": os.path.getsize(paths.config_path())})
    return {"home": paths.home(), "output_dir": paths.output_dir(), "items": items}


def _rm(p):
    def fix(func, path, _e):
        os.chmod(path, 0o700)
        func(path)
    shutil.rmtree(p, onerror=fix)


def run_uninstall() -> dict:
    """Apaga só o que o app criou (arte + config). Seus sprites gerados NUNCA são tocados."""
    removed, failed = [], []
    for it in scan()["items"]:
        try:
            if it["id"] == "art":
                _rm(paths.art_dir())
            else:
                os.remove(paths.config_path())
            removed.append(it["label"])
        except OSError as e:
            failed.append(f"{it['label']}: {e}")
    try:
        os.rmdir(paths.home())
    except OSError:
        pass
    return {"removed": removed, "failed": failed}


def pick_folder(initial: str | None = None) -> str | None:
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as e:
        raise RuntimeError("Não consegui abrir o seletor de pastas. Digite o caminho.") from e
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            init = initial if initial and os.path.isdir(initial) else os.path.expanduser("~")
            chosen = filedialog.askdirectory(initialdir=init, mustexist=False, parent=root,
                                             title="Onde salvar as sprite sheets?")
        finally:
            root.destroy()
    except Exception as e:                                         # noqa: BLE001
        raise RuntimeError("Não consegui abrir o seletor de pastas. Digite o caminho.") from e
    return os.path.abspath(chosen) if chosen else None
