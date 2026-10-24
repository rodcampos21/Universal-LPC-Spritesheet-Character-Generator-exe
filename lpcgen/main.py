"""Ponto de entrada: abre o servidor local numa janela de app (Edge/Chrome)."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "lpcgen"

from lpcgen import server, uninstall                                 # noqa: E402

IDLE_EXIT_SECONDS = 90


def _app_window(url: str) -> bool:
    cands = []
    if os.name == "nt":
        for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    else:
        cands += [shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")]
    for exe in cands:
        if exe and os.path.isfile(exe):
            try:
                subprocess.Popen([exe, f"--app={url}", "--window-size=1280,880"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                continue
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LPC Sprite Gerador")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--home", help="pasta de dados (padrão: ~/LPC Sprite Gerador)")
    ap.add_argument("--uninstall", action="store_true", help="remove a arte baixada e as configurações")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    if args.home:
        os.environ["LPCGEN_HOME"] = args.home
    if args.uninstall:
        info = uninstall.scan()
        print(f"Pasta do app: {info['home']}")
        for it in info["items"]:
            print(f"  - {it['label']}: {it['bytes'] / 1048576:.0f} MB")
        if not args.yes and input("Remover? (s/N) ").strip().lower() not in ("s", "sim", "y", "yes"):
            print("Nada foi removido.")
            return 1
        rep = uninstall.run_uninstall()
        print("Removido:", ", ".join(rep["removed"]) or "nada")
        for f in rep["failed"]:
            print("Falhou:", f)
        print("Seus sprites gerados não foram tocados. Se quiser, apague também o .exe.")
        return 0 if not rep["failed"] else 2
    app = server.App()
    httpd, port = server.start(app, args.port)
    url = f"http://127.0.0.1:{port}/"
    print(f"LPC Sprite Gerador em {url}", flush=True)
    if not args.no_browser and not _app_window(url):
        webbrowser.open(url)
    started = time.time()
    try:
        while not app.stop.wait(2):
            if app.jobs.active():
                continue
            quiet = time.time() - (app.last_ping or started)
            if quiet > (IDLE_EXIT_SECONDS if app.last_ping else 300):
                break
    except KeyboardInterrupt:
        pass
    httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
