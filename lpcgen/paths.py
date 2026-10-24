"""Pastas do app. Tudo que o app cria fica em UMA pasta (para o desinstalador saber o que apagar)."""
from __future__ import annotations

import json
import os


def home() -> str:
    env = os.environ.get("LPCGEN_HOME")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), "LPC Sprite Gerador")


ART_NAME = "LPC Arte"


def art_dir() -> str:
    """Onde fica a arte do LPC (o 'banco de dados'): pasta escolhida + 'LPC Arte'."""
    env = os.environ.get("LPCGEN_ART")
    if env:
        return env
    return load_config().get("art_dir") or os.path.join(home(), ART_NAME)


def art_dir_for(chosen: str) -> str:
    """Sempre cria uma subpasta própria, para o desinstalador nunca apagar arquivos seus."""
    chosen = os.path.abspath(chosen)
    return chosen if os.path.basename(chosen) == ART_NAME else os.path.join(chosen, ART_NAME)


def config_path() -> str:
    return os.path.join(home(), "config.json")


def default_output() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents", "LPC Sprites") \
        if os.name == "nt" else os.path.join(os.path.expanduser("~"), "LPC Sprites")


def load_config() -> dict:
    try:
        with open(config_path(), encoding="utf-8") as fh:
            d = json.load(fh)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(**kw) -> dict:
    cfg = load_config()
    cfg.update(kw)
    os.makedirs(home(), exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    return cfg


def output_dir() -> str:
    return load_config().get("output_dir") or default_output()
