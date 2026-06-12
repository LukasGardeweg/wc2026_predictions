# -*- coding: utf-8 -*-
"""
scraper_oddspedia_during_wm.py
Scraped 1X2-Quoten (Heimsieg / Unentschieden / Heimniederlage) für die
Deutschland-Spiele aus wm_matches_during.MATCHES von Oddspedia.

Buchmacher: bet365, Bwin (gleiche wie Langzeitwetten)
Output: raw_data_during_wm/wm2026_oddspedia_during_wm.xlsx
        (wird bei jedem Lauf komplett überschrieben, kein Zeitverlauf)

Verwendet undetected_chromedriver wegen Cloudflare-Schutz.

HINWEIS: Die Markt-ID für den 1X2-Markt (OT_1X2) ist ein Best-Guess (1, die
übliche ID für "Match Winner" / "1X2" in Odds-APIs). Liefert die getOdds-API
für ein Spiel keine Treffer, im Browser (nicht-headless) die Netzwerk-Anfragen
auf der Match-Seite prüfen (DevTools -> Network -> "getOdds"/"getOdd*") und
OT_1X2 entsprechend anpassen.

Verwendung:
    python scraper_oddspedia_during_wm.py
    python scraper_oddspedia_during_wm.py --headless
"""

import json
import os
import sys
import time

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from deprecated.wm_matches_during import MATCHES, OUTCOMES

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
RAW_DIR   = os.path.join(BASE_DIR, "raw_data_during_wm")

WETTSTEUER = 0
GEO_CODE   = "DE"
LANGUAGE   = "de"
OT_1X2     = 1  # Markt-ID "1X2"/Match Winner - ggf. anpassen, falls Ergebnis leer bleibt

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
    return uc.Chrome(options=opts, version_main=147, headless=headless)


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

def _get_match_odds_from_vue(driver) -> list | None:
    """Versucht, die 1X2-Buchmacher-Odds aus dem Vue/Nuxt-State der Match-Seite
    zu lesen (Liste von Einträgen mit bookie_name + o1/ox/o2)."""
    raw = driver.execute_script("""
        try {
            var app = document.querySelector('#__nuxt').__vue__;
            function find(v, depth) {
                if (!v || depth > 10) return null;
                var d = v.$data;
                if (d) {
                    for (var key of Object.keys(d)) {
                        var val = d[key];
                        if (!val || typeof val !== 'object') continue;
                        var s;
                        try { s = JSON.stringify(val); } catch(e) { continue; }
                        if (s.length > 300000) continue;
                        if (s.indexOf('"o1"') !== -1 && s.indexOf('"ox"') !== -1 && s.indexOf('bookie_name') !== -1) {
                            return val;
                        }
                    }
                }
                for (var c of (v.$children || [])) { var r = find(c, depth+1); if (r) return r; }
                return null;
            }
            var mo = find(app, 0);
            return mo ? JSON.stringify(mo) : null;
        } catch(e) { return null; }
    """)
    if not raw:
        return None
    data = json.loads(raw)
    return _flatten_odds_entries(data)


def _flatten_odds_entries(data) -> list:
    """Normalisiert das gefundene Odds-Objekt (dict oder list) zu einer flachen
    Liste von Einträgen mit bookie_name/o1/ox/o2."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Werte können verschachtelt sein (z.B. {"1": [...]})
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict) and "bookie_name" in value[0]:
                return value
    return []


def _get_match_odds_via_api(driver, event_id: int) -> list:
    """Fallback: ruft die getOdds-API für das Match direkt auf."""
    path = _build_path(
        "getOdds",
        geoCode=GEO_CODE, geoState="", eventId=event_id,
        wettsteuer=WETTSTEUER, ot=OT_1X2, language=LANGUAGE,
    )
    data = _xhr(driver, path)
    inner = data.get("data", {})
    if isinstance(inner, dict):
        return inner.get(str(OT_1X2), [])
    if isinstance(inner, list):
        return inner
    return []


def _extract_1x2(entries: list) -> dict:
    """Filtert auf bet365/Bwin und mappt o1/ox/o2 -> Heimsieg/Unentschieden/Heimniederlage."""
    result: dict[str, dict] = {o: {} for o in OUTCOMES}
    for entry in entries:
        bname = entry.get("bookie_name", "")
        if bname.lower() not in TARGET_BOOKMAKERS:
            continue
        mapping = {"Heimsieg": "o1", "Unentschieden": "ox", "Heimniederlage": "o2"}
        for outcome, field in mapping.items():
            odd = entry.get(field)
            if odd is not None:
                try:
                    result[outcome][bname] = float(odd)
                except (TypeError, ValueError):
                    pass
    return result


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape_match(driver, match: dict) -> list[dict]:
    url = f"https://oddspedia.com/de/fussball/{match['oddspedia_slug']}-{match['oddspedia_event_id']}"
    print(f"  Öffne {url} ...")
    driver.get(url)
    wait = WebDriverWait(driver, 40)

    # Cookie-Banner
    for sel in ["button#onetrust-accept-btn-handler", "button[class*='accept']"]:
        try:
            WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            ).click()
            print("    Cookie-Banner akzeptiert.")
            time.sleep(1)
            break
        except Exception:
            pass

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
    except Exception:
        pass
    time.sleep(3)

    entries = _get_match_odds_from_vue(driver)
    source = "Vue-State"
    if not entries:
        try:
            entries = _get_match_odds_via_api(driver, match["oddspedia_event_id"])
            source = "getOdds-API"
        except Exception as e:
            print(f"    WARNUNG getOdds-API: {e}")
            entries = []

    if not entries:
        print("    Keine 1X2-Odds gefunden (weder Vue-State noch getOdds-API).")
        print("    -> Im Browser (nicht-headless) DevTools/Network prüfen und")
        print("       OT_1X2 / Endpoint in scraper_oddspedia_during_wm.py anpassen.")
        return [
            {
                "Spiel_ID": match["id"], "Heimteam": match["heimteam"],
                "Gastteam": match["gastteam"], "Datum": match["datum"],
                "Ausgang": outcome,
            }
            for outcome in OUTCOMES
        ]

    odds_by_outcome = _extract_1x2(entries)
    print(f"    Odds via {source}: {odds_by_outcome}")

    rows = []
    for outcome in OUTCOMES:
        row = {
            "Spiel_ID": match["id"], "Heimteam": match["heimteam"],
            "Gastteam": match["gastteam"], "Datum": match["datum"],
            "Ausgang": outcome,
        }
        for bname, odd in odds_by_outcome.get(outcome, {}).items():
            # Kanonische Schreibweise (bet365 / Bwin)
            canonical = "bet365" if bname.lower() == "bet365" else "Bwin"
            row[canonical] = odd
        rows.append(row)
    return rows


def scrape(headless: bool = False) -> list[dict]:
    print("[1/2] Starte Browser ...")
    driver = _make_driver(headless=headless)
    all_rows: list[dict] = []

    try:
        for i, match in enumerate(MATCHES, start=1):
            print(f"[1/2] Spiel {i}/{len(MATCHES)}: {match['heimteam']} - {match['gastteam']} ({match['datum']})")
            try:
                all_rows.extend(scrape_match(driver, match))
            except Exception as e:
                print(f"    FEHLER bei {match['id']}: {e}")
            time.sleep(1)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return all_rows


# ---------------------------------------------------------------------------
# Excel speichern
# ---------------------------------------------------------------------------

def save_excel(rows: list[dict]) -> str:
    os.makedirs(RAW_DIR, exist_ok=True)
    filepath = os.path.join(RAW_DIR, "wm2026_oddspedia_during_wm.xlsx")

    bk_cols = ["bet365", "Bwin"]
    columns = ["Spiel_ID", "Heimteam", "Gastteam", "Datum", "Ausgang"] + bk_cols

    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]

    for col in bk_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    spiel_order   = {m["id"]: i for i, m in enumerate(MATCHES)}
    ausgang_order = {o: i for i, o in enumerate(OUTCOMES)}
    df["_spiel_sort"]   = df["Spiel_ID"].map(spiel_order)
    df["_ausgang_sort"] = df["Ausgang"].map(ausgang_order)
    df = df.sort_values(["_spiel_sort", "_ausgang_sort"]).drop(columns=["_spiel_sort", "_ausgang_sort"])
    df = df.reset_index(drop=True)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Oddspedia 1X2")
        ws = writer.sheets["Oddspedia 1X2"]
        for col_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = width

    print(f"[2/2] Gespeichert: {filepath}  ({len(df)} Zeilen, {len(MATCHES)} Spiele)")
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

    df = pd.DataFrame(rows)
    print("\nVorschau:")
    preview_cols = [c for c in ["Spiel_ID", "Ausgang", "bet365", "Bwin"] if c in df.columns]
    print(df[preview_cols].to_string(index=False))


if __name__ == "__main__":
    main(headless="--headless" in sys.argv)
