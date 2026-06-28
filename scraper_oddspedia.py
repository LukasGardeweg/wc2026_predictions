# -*- coding: utf-8 -*-
"""
scraper_oddspedia.py
Scraped aktuelle WM 2026 Langzeitwetten von Oddspedia.
Buchmacher: bet365, Bwin
Output: raw_data_pre_wm/wm2026_oddspedia_DD.MM.YYYY.xlsx

Verwendet undetected_chromedriver wegen Cloudflare-Schutz.

Verwendung:
    python scraper_oddspedia.py
    python scraper_oddspedia.py --headless
"""

import json
import os
import sys
import time
from datetime import datetime

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import wm_paths

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
RAW_DIR   = wm_paths.raw_dir()
URL       = "https://oddspedia.com/de/fussball/international/weltmeisterschaft/langzeitwetten"

LEAGUE_ID  = 3
WETTSTEUER = 0
GEO_CODE   = "DE"
LANGUAGE   = "de"
OT         = 1500  # Markt-ID: WM-Sieger

TARGET_BOOKMAKERS = {"bet365", "bwin"}  # Kleinschreibung zum Vergleich


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

def _make_driver(headless: bool = False) -> uc.Chrome:
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    if headless:
        opts.add_argument("--headless=new")
    return uc.Chrome(options=opts, version_main=149, headless=headless)


# ---------------------------------------------------------------------------
# API via Browser-XHR (umgeht Cloudflare durch Session-Cookies)
# ---------------------------------------------------------------------------

def _xhr(driver, path: str, timeout: int = 15) -> dict:
    result = driver.execute_async_script(f"""
        var done = arguments[0];
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '{path}', true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.onload = function() {{ done(this.responseText); }};
        xhr.onerror = function() {{ done('ERROR'); }};
        xhr.timeout = {timeout * 1000};
        xhr.ontimeout = function() {{ done('TIMEOUT'); }};
        xhr.send();
    """)
    if result in ("ERROR", "TIMEOUT") or not result:
        raise RuntimeError(f"XHR fehlgeschlagen: {path}")
    return json.loads(result)


def _build_path(endpoint: str, **params) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/api/v1/{endpoint}?{qs}"


# ---------------------------------------------------------------------------
# Daten extrahieren
# ---------------------------------------------------------------------------

def _get_all_teams(driver) -> list[dict]:
    raw = driver.execute_script("""
        try {
            var app = document.querySelector('#__nuxt').__vue__;
            function find(v, depth) {
                if (!v || depth > 8) return null;
                var d = v.$data;
                if (d && d.outrights && d.outrights.max_odds) return d.outrights.max_odds;
                for (var c of (v.$children || [])) { var r = find(c, depth+1); if (r) return r; }
                return null;
            }
            var mo = find(app, 0);
            return mo ? JSON.stringify(mo) : null;
        } catch(e) { return null; }
    """)
    if raw:
        max_odds = json.loads(raw)
        entries  = max_odds.get(str(OT), [])
        return [{"team_name": e["team_name"], "team_id": e["team_id"]} for e in entries]

    print("  Vue-State nicht verfügbar, verwende getOutrights API ...")
    data = _xhr(driver, _build_path(
        "getOutrights",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", language=LANGUAGE
    ))
    return [
        {"team_name": e["team_name"], "team_id": e["team_id"]}
        for e in data.get("data", {}).get(str(OT), [])
    ]


def _get_current_odds(driver, team_id: int) -> dict:
    """Gibt {Buchmachername: Quote} nur für bet365 und Bwin zurück."""
    path = _build_path(
        "getOutrightsSingle",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", teamId=team_id, language=LANGUAGE
    )
    data = _xhr(driver, path)
    result = {}
    for entry in data.get("data", []):
        bname = entry.get("bookie_name", "")
        if bname.lower() in TARGET_BOOKMAKERS:
            odd = entry.get("o1")
            if odd is not None:
                result[bname] = float(odd)
    return result


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape(headless: bool = False) -> list[dict]:
    print(f"[1/3] Starte Browser -> {URL}")
    driver = _make_driver(headless=headless)

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 40)

        # Cookie-Banner
        for sel in ["button#onetrust-accept-btn-handler", "button[class*='accept']"]:
            try:
                WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                ).click()
                print("  Cookie-Banner akzeptiert.")
                time.sleep(1)
                break
            except Exception:
                pass

        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".outrights-table-row")
            ))
        except Exception:
            pass
        time.sleep(3)

        print("[2/3] Extrahiere Teams ...")
        teams = _get_all_teams(driver)
        if not teams:
            raise RuntimeError("Keine Teams gefunden.")
        print(f"  {len(teams)} Teams.")

        print("[3/3] Lade aktuelle Quoten (bet365, Bwin) ...")
        rows = []
        for i, team in enumerate(teams):
            tname = team["team_name"]
            tid   = team["team_id"]
            print(f"  [{i+1}/{len(teams)}] {tname}", end="  ")
            try:
                odds = _get_current_odds(driver, tid)
                print({k: v for k, v in odds.items()})
            except Exception as e:
                print(f"WARNUNG: {e}")
                odds = {}
            row = {"Team": tname}
            row.update(odds)
            rows.append(row)
            time.sleep(0.4)

        return rows

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Excel speichern
# ---------------------------------------------------------------------------

def save_excel(rows: list[dict]) -> str:
    df = pd.DataFrame(rows)

    # Nur Zielbuchmacher behalten, Quoten numerisch
    bk_cols = [c for c in df.columns if c != "Team" and c.lower() in TARGET_BOOKMAKERS]
    df = df[["Team"] + bk_cols]
    for col in bk_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Favoriten oben (niedrigste Quote = höchste Wahrscheinlichkeit)
    if bk_cols:
        df["_avg"] = df[bk_cols].mean(axis=1, skipna=True)
        df = df.sort_values("_avg").drop(columns="_avg")

    df = df.reset_index(drop=True)
    today    = datetime.now().strftime("%d.%m.%Y")
    filepath = os.path.join(RAW_DIR, f"wm2026_oddspedia_{today}.xlsx")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="WM2026 Odds")
        ws = writer.sheets["WM2026 Odds"]
        for col_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = width

    missing = [bk for bk in ["bet365", "Bwin"] if bk not in bk_cols
               and bk.lower() not in [c.lower() for c in bk_cols]]
    if missing:
        print(f"  Hinweis: {missing} nicht gefunden (für Deutschland evtl. gesperrt?)")

    print(f"Gespeichert: {filepath}  ({len(df)} Teams, Buchmacher: {bk_cols})")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(headless: bool = False):
    rows = scrape(headless=headless)
    if not rows:
        print("Keine Daten extrahiert.")
        return
    save_excel(rows)
    print("\nFertig!")


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    main(headless=headless)
