# -*- coding: utf-8 -*-
"""
wm_paths.py

Zentrale Pfad-Logik für den automatischen Wechsel von der Vor-WM-Phase zur
WM-Phase: Ab WM_START_DATE schreiben Scraper und Verarbeitung der
Langzeitwetten (WM-Sieger) automatisch in die during_wm-Ordner statt in die
pre_wm-Ordner. Die pre_wm-Daten bleiben dabei unverändert als historische
Basis erhalten.

Verwendung:
    import wm_paths
    RAW_DIR        = wm_paths.raw_dir()
    PROCESSED_FILE = wm_paths.processed_long_file()
    WIDE_FILE      = wm_paths.processed_wide_file()
"""

import os
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))

WM_START_DATE = date(2026, 6, 11)


def during_wm() -> bool:
    """True ab dem WM-Start (11.06.2026)."""
    return date.today() >= WM_START_DATE


def raw_dir() -> str:
    name = "raw_data_during_wm" if during_wm() else "raw_data_pre_wm"
    return os.path.join(BASE, name)


def processed_dir() -> str:
    name = "processed_data_during_wm" if during_wm() else "processed_data_pre_wm"
    return os.path.join(BASE, name)


def processed_long_file() -> str:
    return os.path.join(processed_dir(), "processed_data_long.xlsx")


def processed_wide_file() -> str:
    return os.path.join(processed_dir(), "processed_data_wide.xlsx")
