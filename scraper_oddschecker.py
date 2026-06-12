"""
Oddschecker World Cup 2026 Odds Scraper
Columns: Team | Unibet | Ladbrokes | Betway | Betfair | <alle weiteren Buchmacher A-Z>
"""

import time
from datetime import datetime

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.oddschecker.com/football/world-cup/winner"

# Prioritäts-Buchmacher (feste data-bk Codes, kommen zuerst in der Excel-Datei)
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


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def _resolve_name(code: str, dom_names: dict) -> str:
    """Code -> Klartext: DOM zuerst, dann Fallback-Dict, dann Code selbst."""
    name = dom_names.get(code, "")
    if name and name != code:
        return name
    return OC_CODE_TO_NAME.get(code, code)


def scrape(url: str = URL, headless: bool = False) -> tuple[dict, list[dict]]:
    print(f"[1/3] Öffne {url} ...")
    driver = _make_driver(headless=headless)

    try:
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
                print("  Cookie-Banner akzeptiert.")
                time.sleep(1)
                break
            except Exception:
                pass

        # Tabelle abwarten
        print("[1/3] Warte auf Odds-Tabelle ...")
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
                print("  Auf Decimal-Odds umgeschaltet.")
                time.sleep(1.5)
                break
            except Exception:
                pass

        # Warten bis data-odig befüllt ist
        print("[1/3] Warte auf befüllte Odds-Werte ...")

        def odds_ready(d):
            els = d.find_elements(By.CSS_SELECTOR, "[data-odig]")
            return any(e.get_attribute("data-odig") for e in els[:20])

        try:
            wait.until(odds_ready)
            print("  Odds-Werte geladen.")
        except Exception:
            print("  Timeout – parse trotzdem.")

        time.sleep(2)

        print("[2/3] Extrahiere alle Buchmacher aus Live-DOM ...")
        result = driver.execute_script(_JS_EXTRACT)

        if result.get("error"):
            raise RuntimeError(result["error"])

        dom_names = result.get("codeToName", {})
        raw_rows  = result.get("results", [])

        # Code -> Klartextname auflösen (DOM + Fallback-Dict)
        all_codes = sorted({
            key[len("__code__"):]
            for row in raw_rows
            for key in row
            if key.startswith("__code__")
        })
        # Zwei-Phasen-Deduplication: erst zählen, dann umbenennen
        raw_names = {code: _resolve_name(code, dom_names) for code in all_codes}
        name_freq: dict[str, int] = {}
        for name in raw_names.values():
            name_freq[name] = name_freq.get(name, 0) + 1

        code_to_name: dict[str, str] = {}
        for code, name in raw_names.items():
            code_to_name[code] = f"{name} ({code})" if name_freq[name] > 1 else name

        print(f"  Buchmacher gefunden: {code_to_name}")

        # Rohdaten in lesbare Spaltennamen übersetzen
        data = []
        for raw in raw_rows:
            row = {"Team": raw["Team"]}
            for code in all_codes:
                name = code_to_name[code]
                row[name] = raw.get("__code__" + code)
            data.append(row)

        print(f"  {len(data)} Teams extrahiert.")
        return code_to_name, data

    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def save_excel(code_to_name: dict, data: list[dict], filepath: str | None = None) -> str:
    if not filepath:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"wm2026_odds_{ts}.xlsx"

    df = pd.DataFrame(data)

    # Letzter Sicherheitsnetz: doppelte Spaltennamen mit Suffix auflösen
    if df.columns.duplicated().any():
        seen_cols: dict[str, int] = {}
        new_cols = []
        for col in df.columns:
            if col in seen_cols:
                seen_cols[col] += 1
                new_cols.append(f"{col}_{seen_cols[col]}")
            else:
                seen_cols[col] = 0
                new_cols.append(col)
        df.columns = new_cols

    # Prioritäts-Spalten auf kanonische Namen umbenennen & Reihenfolge festlegen
    priority_names = list(PRIORITY.keys())   # ["Unibet", "Ladbrokes", "Betway", "Betfair"]
    priority_resolved = {}

    for canonical, code in PRIORITY.items():
        resolved = code_to_name.get(code, code)
        if resolved in df.columns and resolved != canonical and canonical not in df.columns:
            priority_resolved[resolved] = canonical

    df = df.rename(columns=priority_resolved)

    # Spalten einteilen
    all_bk_cols  = [c for c in df.columns if c != "Team"]
    present_prio = [c for c in priority_names if c in all_bk_cols]
    rest_cols    = sorted(c for c in all_bk_cols if c not in present_prio)

    ordered_cols = ["Team"] + present_prio + rest_cols
    ordered_cols = [c for c in ordered_cols if c in df.columns]
    df = df[ordered_cols]

    # Odds numerisch
    for col in df.columns:
        if col != "Team":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Favoriten zuerst (Spanien oben, Außenseiter unten)
    num_cols = [c for c in df.columns if c != "Team"]
    if num_cols:
        df["_avg"] = df[num_cols].mean(axis=1, skipna=True)
        df = df.sort_values("_avg", ascending=True).drop(columns="_avg")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="WM2026 Odds")
        ws = writer.sheets["WM2026 Odds"]
        for col_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = width

    print(f"[3/3] Gespeichert: {filepath}  ({len(df)} Teams, {len(ordered_cols)-1} Buchmacher)")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(headless: bool = False):
    code_to_name, data = scrape(URL, headless=headless)

    if not data:
        print("Keine Daten extrahiert.")
        return

    filepath = save_excel(code_to_name, data)
    print(f"\nFertig! Datei: {filepath}")

    df = pd.DataFrame(data)
    print(f"\nSpalten: {list(df.columns)}")
    print("\nVorschau (Top 5, erste 6 Buchmacher):")
    preview_cols = ["Team"] + [c for c in df.columns if c != "Team"][:6]
    print(df[preview_cols].head(5).to_string(index=False))


if __name__ == "__main__":
    main(headless=False)
