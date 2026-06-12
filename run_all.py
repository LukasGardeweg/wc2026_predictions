# -*- coding: utf-8 -*-
"""
run_all.py
Vollautomatischer WM 2026 Daten-Update.

Ablauf:
  1. Wettfreunde scrapen  -> raw_data_pre_wm/wm2026_wettfreunde_DD.MM.YYYY.xlsx
  2. Oddspedia scrapen    -> raw_data_pre_wm/wm2026_oddspedia_DD.MM.YYYY.xlsx
  3. Oddschecker scrapen  -> raw_data_pre_wm/wm2026_oddschecker_DD.MM.YYYY.xlsx
  4. processed_data_long.xlsx mit neuen Daten erweitern
  5. PNG-Charts (Balkendiagramm & Zeitverlauf) fuer README aktualisieren

Verwendung:
    python run_all.py             # Browser sichtbar
    python run_all.py --headless  # Browser im Hintergrund
"""

import os
import sys
import traceback
from datetime import datetime

import wm_paths

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE    = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = wm_paths.raw_dir()


# ---------------------------------------------------------------------------
# Hilfsfunktion: Schritt-Header
# ---------------------------------------------------------------------------

TOTAL_STEPS = 5


def _header(step: int, total: int, title: str):
    print()
    print(f"{'=' * 60}")
    print(f"  Schritt {step}/{total}: {title}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Scraper-Aufrufe
# ---------------------------------------------------------------------------

def run_wettfreunde() -> bool:
    _header(1, TOTAL_STEPS, "Wettfreunde  (Interwetten)")
    try:
        import scraper_wettfreunde
        scraper_wettfreunde.main()
        return True
    except Exception:
        print("  FEHLER beim Wettfreunde-Scraper:")
        traceback.print_exc()
        return False


def run_oddspedia(headless: bool) -> bool:
    _header(2, TOTAL_STEPS, "Oddspedia  (bet365, Bwin)")
    try:
        import scraper_oddspedia
        scraper_oddspedia.main(headless=headless)
        return True
    except Exception:
        print("  FEHLER beim Oddspedia-Scraper:")
        traceback.print_exc()
        return False


def run_oddschecker(headless: bool) -> bool:
    _header(3, TOTAL_STEPS, "Oddschecker  (Unibet, Ladbrokes, Betway, Betfair)")
    try:
        from scraper_oddschecker import scrape, save_excel

        code_to_name, data = scrape(headless=headless)
        if not data:
            print("  Keine Daten extrahiert.")
            return False

        today    = datetime.now().strftime("%d.%m.%Y")
        filepath = os.path.join(RAW_DIR, f"wm2026_oddschecker_{today}.xlsx")
        save_excel(code_to_name, data, filepath=filepath)
        return True
    except Exception:
        print("  FEHLER beim Oddschecker-Scraper:")
        traceback.print_exc()
        return False


def run_update() -> bool:
    _header(4, TOTAL_STEPS, "processed_data_long.xlsx aktualisieren")
    try:
        import update_processed_data
        update_processed_data.main()
        return True
    except Exception:
        print("  FEHLER beim Update:")
        traceback.print_exc()
        return False


def run_png_charts() -> bool:
    _header(5, TOTAL_STEPS, "PNG-Charts aktualisieren (Balkendiagramm & Zeitverlauf)")
    try:
        sys.path.insert(0, os.path.join(BASE, "visualization_png"))
        import create_png_charts
        create_png_charts.main()
        return True
    except Exception:
        print("  FEHLER beim Erzeugen der PNG-Charts:")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    headless = "--headless" in sys.argv

    phase = "WAEHREND DER WM" if wm_paths.during_wm() else "VOR DER WM"

    print()
    print("=" * 60)
    print("  WM 2026 - Vollautomatischer Daten-Update")
    print(f"  {datetime.now().strftime('%d.%m.%Y  %H:%M:%S')}  -  Phase: {phase}")
    print(f"  Rohdaten     -> {os.path.relpath(RAW_DIR, BASE)}")
    print(f"  Verarbeitet  -> {os.path.relpath(wm_paths.processed_dir(), BASE)}")
    print("=" * 60)

    results = {
        "Wettfreunde":  run_wettfreunde(),
        "Oddspedia":    run_oddspedia(headless),
        "Oddschecker":  run_oddschecker(headless),
        "Update":       run_update(),
        "PNG-Charts":   run_png_charts(),
    }

    # Zusammenfassung
    print()
    print("=" * 60)
    print("  Zusammenfassung")
    print("=" * 60)
    for name, ok in results.items():
        status = "OK" if ok else "FEHLER"
        print(f"  {name:<20} {status}")

    all_ok = all(results.values())
    print()
    if all_ok:
        print("  Alle Schritte erfolgreich abgeschlossen.")
    else:
        failed = [n for n, ok in results.items() if not ok]
        print(f"  Fehler bei: {', '.join(failed)}")
        print("  Die Update-Datei wurde trotzdem mit den verfuegbaren Daten befuellt.")
    print()


if __name__ == "__main__":
    main()
