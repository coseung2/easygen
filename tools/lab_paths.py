"""Shared path configuration for standalone Lab and episode scripts."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("MODAL_GUI_DATA_ROOT", REPO_ROOT / "data")).expanduser()
FONT_ROOT = Path(os.environ["MODAL_GUI_FONT_ROOT"]).expanduser() if os.environ.get("MODAL_GUI_FONT_ROOT") else None


def data_path(*parts: str) -> Path:
    """Resolve generated/source data beneath the configured external data root."""
    return DATA_ROOT.joinpath(*parts)


def lab_path(*parts: str) -> Path:
    """Resolve a script's Lab workspace beneath the configured data root."""
    return data_path("lab", *parts)


def series_path(*parts: str) -> Path:
    """Resolve episode assets beneath the configured data root."""
    return data_path("series", *parts)


def font_path(filename: str, *fallbacks: str) -> Path:
    """Find a font in the configured font root, then common system/repo roots."""
    roots = [FONT_ROOT] if FONT_ROOT else []
    roots += [Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
              Path("C:/Windows/Fonts"), REPO_ROOT / "pipelines/_shared/fonts"]
    for name in (filename, *fallbacks):
        for root in roots:
            candidate = root / name
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"Font not found: {filename}; set MODAL_GUI_FONT_ROOT")
