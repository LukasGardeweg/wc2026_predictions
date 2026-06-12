# -*- coding: utf-8 -*-
"""
scraper_wettfreunde.py
Scraped aktuelle WM 2026 Langzeitwetten von Wettfreunde.
Buchmacher: Interwetten
Output: raw_data_pre_wm/wm2026_wettfreunde_DD.MM.YYYY.xlsx

Verwendung:
    python scraper_wettfreunde.py
"""

import os
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

import wm_paths

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
RAW_DIR   = wm_paths.raw_dir()
URL       = "https://www.wettfreunde.net/wm-2026/"
TARGET_BK = "interwetten"  # URL-Keyword zur Spaltenidentifikation

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape() -> list[dict]:
    print(f"[1/2] Lade {URL}")
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Vergleichstabelle: erste Tabelle mit >= 5 Spalten
    tables = soup.find_all("table")
    comparison_table = None
    for t in tables:
        header_row = t.find("tr")
        if not header_row:
            continue
        if len(header_row.find_all(["th", "td"])) >= 5:
            comparison_table = t
            break

    if comparison_table is None:
        raise RuntimeError("Keine Vergleichstabelle gefunden.")

    # Interwetten-Spalte per Link-URL im Header identifizieren
    header_cells = comparison_table.find("tr").find_all(["th", "td"])
    interwetten_col = None
    for i, cell in enumerate(header_cells):
        for a in cell.find_all("a"):
            if TARGET_BK in a.get("href", "").lower():
                interwetten_col = i
                break
        if interwetten_col is not None:
            break

    if interwetten_col is None:
        header_texts = [c.get_text(strip=True)[:30] for c in header_cells]
        raise RuntimeError(
            f"Interwetten-Spalte nicht gefunden.\nHeader: {header_texts}"
        )

    print(f"  Interwetten in Spalte {interwetten_col} gefunden.")

    # Datenzeilen extrahieren
    print("[2/2] Extrahiere Quoten ...")
    rows = []
    for tr in comparison_table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= interwetten_col:
            continue
        team = cells[0].get_text(strip=True)
        if not team:
            continue
        odds_text = cells[interwetten_col].get_text(strip=True).replace(",", ".")
        try:
            odds_val = float(odds_text)
        except ValueError:
            continue
        rows.append({"Team": team, "Interwetten": odds_val})
        print(f"  {team}: {odds_val}")

    print(f"\n  {len(rows)} Teams extrahiert.")
    return rows


# ---------------------------------------------------------------------------
# Excel speichern
# ---------------------------------------------------------------------------

def save_excel(rows: list[dict]) -> str:
    df = pd.DataFrame(rows)
    df = df.sort_values("Interwetten").reset_index(drop=True)

    today    = datetime.now().strftime("%d.%m.%Y")
    filepath = os.path.join(RAW_DIR, f"wm2026_wettfreunde_{today}.xlsx")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="WM2026 Odds")
        ws = writer.sheets["WM2026 Odds"]
        for col_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = width

    print(f"Gespeichert: {filepath}  ({len(df)} Teams, Buchmacher: Interwetten)")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    rows = scrape()
    if not rows:
        print("Keine Daten extrahiert.")
        return
    save_excel(rows)
    print("\nFertig!")


if __name__ == "__main__":
    main()
