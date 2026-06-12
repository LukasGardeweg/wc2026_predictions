# -*- coding: utf-8 -*-
"""
scraper_oddschecker_during_wm.py
Scraped 1X2-Quoten (Heimsieg / Unentschieden / Heimniederlage) für die
Deutschland-Spiele aus wm_matches_during.MATCHES von Oddschecker.

Buchmacher: Unibet, Ladbrokes, Betway, Betfair (gleiche wie Langzeitwetten)
Output: raw_data_during_wm/wm2026_oddschecker_during_wm.xlsx
        (wird bei jedem Lauf komplett überschrieben, kein Zeitverlauf)

Verwendung:
    python scraper_oddschecker_during_wm.py
    python scraper_oddschecker_during_wm.py --headless
"""

import os
import sys
import time
import unicodedata

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from deprecated.wm_matches_during import MATCHES, OUTCOMES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE_DIR, "raw_data_during_wm")

# Prioritäts-Buchmacher (feste data-bk Codes) - gleiche wie scraper_oddschecker.py
PRIORITY = {
    "Unibet":    "UN",
    "Ladbrokes": "LD",
    "Betway":    "BY",
    "Betfair":   "BF",
}

# Bekannte Oddschecker-Kurzbezeichnungen -> Klartextnamen (Fallback falls DOM keinen Namen liefert)
OC_CODE_TO_NAME = {
    "AKB": "AK Bets",
    "B3":  "Bet365",
    "BF":  "Betfair",
    "BRS": "BresBet",
    "BTT": "BetTom",
    "BY":  "Betway",
    "CE":  "Coral",
    "EE":  "888sport",
    "FR":  "Betfred",
    "G5":  "BetMGM UK",
    "KN":  "BetGoodwin",
    "LD":  "Ladbrokes",
    "MA":  "Matchbook",
    "OE":  "BOYLE Sports",
    "PP":  "Paddy Power",
    "PUP": "PricedUp",
    "QN":  "QuinnBet",
    "S6":  "Star Sports",
    "SI":  "Sporting Index",
    "SK":  "Sky Bet",
    "SX":  "Spreadex",
    "UN":  "Unibet",
    "VC":  "BetVictor",
    "VE":  "Virgin Bet",
    "WA":  "10bet",
    "WH":  "William Hill",
}

# ---------------------------------------------------------------------------
# JavaScript: durchsucht den gesamten DOM nach Buchmacher-Namen + Odds
# (identisch zu scraper_oddschecker.py - gleiche Tabellenstruktur auf Match-Seiten)
# ---------------------------------------------------------------------------
_JS_EXTRACT = """
// --- Tabelle finden ---
const table = document.querySelector('table#odds-data-table')
           || document.querySelector('table.eventTable')
           || document.querySelector('table');
if (!table) return {error: 'Keine Tabelle gefunden', codeToName: {}, results: []};

// --- Pass 1: gesamter DOM – alle [data-bk]-Elemente auf Namen prüfen ---
const codeToName = {};
[...document.querySelectorAll('[data-bk]')].forEach(el => {
    const code = el.getAttribute('data-bk');
    if (!code || codeToName[code]) return;

    const candidates = [
        el.getAttribute('title'),
        el.getAttribute('aria-label'),
        el.getAttribute('data-name'),
        el.getAttribute('data-bookmaker'),
        el.querySelector('img')  && el.querySelector('img').getAttribute('alt'),
        el.querySelector('img')  && el.querySelector('img').getAttribute('title'),
        el.querySelector('a')    && el.querySelector('a').getAttribute('title'),
        el.querySelector('span') && el.querySelector('span').getAttribute('title'),
    ].filter(s => s && s.length > 1 && !/^\\d/.test(s.trim()));

    if (candidates.length) codeToName[code] = candidates[0].trim();
});

// --- Pass 2: Header-Zellen über Spaltenposition (ergänzt fehlende Namen) ---
const thead = table.querySelector('thead');
const headerRow = thead ? thead.querySelector('tr') : table.querySelector('tr');
const headerCells = headerRow ? [...headerRow.querySelectorAll('th,td')] : [];

const tbody = table.querySelector('tbody');
const firstDataRow = tbody ? tbody.querySelector('tr') : table.querySelectorAll('tr')[1];
const firstCells = firstDataRow ? [...firstDataRow.querySelectorAll('td,th')] : [];

firstCells.forEach((cell, idx) => {
    const code = cell.getAttribute('data-bk');
    if (!code || codeToName[code]) return;   // schon gefunden
    if (idx >= headerCells.length) return;
    const h = headerCells[idx];
    const name = h.getAttribute('title')
              || (h.querySelector('img') && h.querySelector('img').getAttribute('alt'))
              || (h.querySelector('a')   && h.querySelector('a').getAttribute('title'))
              || h.textContent.trim();
    if (name && name.length > 1 && !/^\\d/.test(name)) codeToName[code] = name.trim();
});

// --- Alle Datenzeilen extrahieren ---
const rows = tbody ? [...tbody.querySelectorAll('tr')] : [...table.querySelectorAll('tr')].slice(1);

const results = [];
rows.forEach(row => {
    const nameCell = row.querySelector('td:not([data-bk]), th:not([data-bk])');
    if (!nameCell) return;
    const team = nameCell.textContent.trim();
    if (!team || ['team','selection','runner',''].includes(team.toLowerCase())) return;

    const rowData = {Team: team};
    [...row.querySelectorAll('[data-bk]')].forEach(cell => {
        const code = cell.getAttribute('data-bk');
        rowData['__code__' + code] = cell.getAttribute('data-odig')
                                  || cell.getAttribute('data-odds')
                                  || cell.textContent.trim()
                                  || null;
    });
    results.push(rowData);
});

return {codeToName, results};
"""


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

def _make_driver(headless: bool = False) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver


def _resolve_name(code: str, dom_names: dict) -> str:
    """Code -> Klartext: DOM zuerst, dann Fallback-Dict, dann Code selbst."""
    name = dom_names.get(code, "")
    if name and name != code:
        return name
    return OC_CODE_TO_NAME.get(code, code)


def _normalize(text: str) -> str:
    """Kleinschreibung + Diakritika entfernen, für robusten Team-Namen-Vergleich."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _row_to_outcome(team_label: str, match: dict) -> str | None:
    """Mappt eine Tabellenzeile (Team-Name) auf Heimsieg/Unentschieden/Heimniederlage."""
    norm = _normalize(team_label)

    if norm in ("draw", "the draw", "tie", "x"):
        return "Unentschieden"
    if norm == _normalize(match["heimteam_en"]):
        return "Heimsieg"
    if norm == _normalize(match["gastteam_en"]):
        return "Heimniederlage"
    return None


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def scrape_match(driver: webdriver.Chrome, match: dict) -> list[dict]:
    """Scraped die 1X2-Quoten für ein Spiel und gibt bis zu 3 Zeilen zurück
    (Heimsieg / Unentschieden / Heimniederlage), jeweils mit Buchmacher-Quoten."""
    url = match["oddschecker_url"]
    print(f"  Öffne {url} ...")
    driver.get(url)
    wait = WebDriverWait(driver, 40)

    # Cookie-Banner
    for sel in [
        "button#onetrust-accept-btn-handler",
        "button[data-testid='cookie-accept']",
        ".js-accept-cookies",
        "[class*='cookie'] button",
    ]:
        try:
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            btn.click()
            print("    Cookie-Banner akzeptiert.")
            time.sleep(1)
            break
        except Exception:
            pass

    # Tabelle abwarten
    for sel in ["table#odds-data-table", "[data-bk]", "tr.diff-row", "table"]:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            break
        except Exception:
            pass

    # Decimal-Odds einschalten
    for sel in ["a[data-format='decimal']", "button[data-format='decimal']", "a[href*='decimal']"]:
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click()
            print("    Auf Decimal-Odds umgeschaltet.")
            time.sleep(1.5)
            break
        except Exception:
            pass

    # Warten bis data-odig befüllt ist
    def odds_ready(d):
        els = d.find_elements(By.CSS_SELECTOR, "[data-odig]")
        return any(e.get_attribute("data-odig") for e in els[:20])

    try:
        wait.until(odds_ready)
    except Exception:
        print("    Timeout – parse trotzdem.")

    time.sleep(2)

    result = driver.execute_script(_JS_EXTRACT)
    if result.get("error"):
        print(f"    FEHLER: {result['error']}")
        return []

    dom_names = result.get("codeToName", {})
    raw_rows  = result.get("results", [])

    rows = []
    for raw in raw_rows:
        outcome = _row_to_outcome(raw["Team"], match)
        if outcome is None:
            continue

        row = {
            "Spiel_ID": match["id"],
            "Heimteam": match["heimteam"],
            "Gastteam": match["gastteam"],
            "Datum":    match["datum"],
            "Ausgang":  outcome,
        }
        for key, value in raw.items():
            if not key.startswith("__code__"):
                continue
            code = key[len("__code__"):]
            name = _resolve_name(code, dom_names)
            if name in PRIORITY:
                row[name] = value
        rows.append(row)

    found = [r["Ausgang"] for r in rows]
    print(f"    Ausgänge gefunden: {found}")
    return rows


def scrape(headless: bool = False) -> list[dict]:
    print(f"[1/2] Starte Browser ...")
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
        driver.quit()

    return all_rows


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def save_excel(rows: list[dict]) -> str:
    os.makedirs(RAW_DIR, exist_ok=True)
    filepath = os.path.join(RAW_DIR, "wm2026_oddschecker_during_wm.xlsx")

    columns = ["Spiel_ID", "Heimteam", "Gastteam", "Datum", "Ausgang"] + list(PRIORITY.keys())
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[columns]

    for col in PRIORITY.keys():
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sortierung: Reihenfolge der Spiele wie in MATCHES, je Spiel Heimsieg/Unentschieden/Heimniederlage
    spiel_order = {m["id"]: i for i, m in enumerate(MATCHES)}
    ausgang_order = {o: i for i, o in enumerate(OUTCOMES)}
    df["_spiel_sort"]   = df["Spiel_ID"].map(spiel_order)
    df["_ausgang_sort"] = df["Ausgang"].map(ausgang_order)
    df = df.sort_values(["_spiel_sort", "_ausgang_sort"]).drop(columns=["_spiel_sort", "_ausgang_sort"])
    df = df.reset_index(drop=True)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Oddschecker 1X2")
        ws = writer.sheets["Oddschecker 1X2"]
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
    preview_cols = ["Spiel_ID", "Ausgang"] + list(PRIORITY.keys())
    preview_cols = [c for c in preview_cols if c in df.columns]
    print(df[preview_cols].to_string(index=False))


if __name__ == "__main__":
    main(headless="--headless" in sys.argv)
