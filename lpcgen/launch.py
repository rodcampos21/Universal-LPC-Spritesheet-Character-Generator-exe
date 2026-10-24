"""Entrada do PyInstaller (e útil na fonte: python lpcgen/launch.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lpcgen.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
