"""
Oddspedia WM 2026 – Historische Quoten-Bewegungen
Quelle: oddspedia.com/de/fussball/international/weltmeisterschaft/langzeitwetten

Ausgabe (Standard):
  Excel mit zwei Sheets
  - "History"  : Datum | Team | Buchmacher | Quote  (Long-Format, alle Bewegungen)
  - "Aktuell"  : Snapshot der aktuellen Quoten

Ausgabe (--snapshot YYYY-MM-DD):
  Excel mit einem Sheet
  - Snapshot der Quoten zum angegebenen Datum (letzter Wert vor/am Datum)
  - Nur Teams, die zu diesem Datum schon im Markt waren
  Hinweis: Teams die danach aus dem Markt genommen wurden (z.B. nach
  Playoff-Ausscheiden) sind NICHT verfügbar – die API liefert nur
  aktive Angebote; historisch geschlossene Offers sind nicht abrufbar.

Verwendung:
    python history.scraper.py
    python history.scraper.py --headless
    python history.scraper.py --snapshot 2026-03-25
    python history.scraper.py --snapshot 2026-03-25 --headless
"""

import sys
import time
from datetime import datetime

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL      = "https://oddspedia.com/de/fussball/international/weltmeisterschaft/langzeitwetten"
LEAGUE_ID = 3
WETTSTEUER = 0
GEO_CODE   = "DE"
LANGUAGE   = "de"
OT         = 1500   # Markt-ID: Gewinner


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
# API-Calls via Browser-XHR (umgeht Cloudflare durch Session-Cookies)
# ---------------------------------------------------------------------------

def _xhr(driver, path: str, timeout: int = 15) -> dict:
    """Führt einen GET-Request im Browser-Kontext aus und gibt das JSON zurück."""
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
    import json
    return json.loads(result)


def _build_path(endpoint: str, **params) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/api/v1/{endpoint}?{qs}"


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------

def _get_all_teams(driver) -> list[dict]:
    """
    Holt alle Teams von der Seite aus dem Vue-State.
    Gibt [{team_name, team_id, sport_id}, ...] zurück.
    """
    # Direkt aus dem Vuex-State lesen (kein Extra-Request nötig)
    import json
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
        entries = max_odds.get(str(OT), [])
        return [{"team_name": e["team_name"], "team_id": e["team_id"]} for e in entries]

    # Fallback: getOutrights API
    print("  Vue-State nicht verfügbar, verwende getOutrights API ...")
    data = _xhr(driver, _build_path(
        "getOutrights",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", language=LANGUAGE
    ))
    teams = []
    for entry in data.get("data", {}).get(str(OT), []):
        teams.append({"team_name": entry["team_name"], "team_id": entry["team_id"]})
    return teams


def _get_offers(driver, team_id: int) -> list[dict]:
    """
    Gibt [{offer_id, bookie_name, current_odds}, ...] für ein Team zurück.
    """
    path = _build_path(
        "getOutrightsSingle",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", teamId=team_id, language=LANGUAGE
    )
    data = _xhr(driver, path)
    return [
        {
            "offer_id":    entry["offer_id"],
            "bookie_name": entry["bookie_name"],
            "current_odd": entry.get("o1"),
        }
        for entry in data.get("data", [])
        if entry.get("offer_id")
    ]


def _get_movements(driver, offer_id: int) -> list[dict]:
    """
    Gibt [{t: datetime_str, y: odds_str}, ...] für ein Angebot zurück.
    """
    path = _build_path(
        "getOutrightsMovements",
        leagueId=LEAGUE_ID, offerId=offer_id, wettsteuer=WETTSTEUER, language=LANGUAGE
    )
    data = _xhr(driver, path)
    return data.get("data", {}).get("moves", [])


def scrape(headless: bool = False) -> tuple[list[dict], list[dict]]:
    """
    Gibt (history_rows, snapshot_rows) zurück.
    history_rows: [{Datum, Team, Buchmacher, Quote}]
    snapshot_rows: [{Team, <bookie>: <current_odd>}]
    """
    print(f"[1/4] Starte Browser und lade {URL} ...")
    driver = _make_driver(headless=headless)

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 40)

        # Cookie-Banner
        for sel in ["button#onetrust-accept-btn-handler", "button[class*='accept']"]:
            try:
                WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel))).click()
                print("  Cookie-Banner akzeptiert.")
                time.sleep(1)
                break
            except Exception:
                pass

        # Warten bis Tabelle geladen
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".outrights-table-row")))
        except Exception:
            pass
        time.sleep(3)

        print("[2/4] Extrahiere Teams ...")
        teams = _get_all_teams(driver)
        if not teams:
            raise RuntimeError("Keine Teams gefunden.")
        print(f"  {len(teams)} Teams: {[t['team_name'] for t in teams]}")

        print("[3/4] Lade Quoten-Offers und historische Bewegungen ...")
        history_rows: list[dict] = []
        snapshot_rows: list[dict] = []

        for i, team in enumerate(teams):
            tname = team["team_name"]
            tid   = team["team_id"]
            print(f"  [{i+1}/{len(teams)}] {tname} (ID={tid})")

            try:
                offers = _get_offers(driver, tid)
            except Exception as e:
                print(f"    WARNUNG Offers: {e}")
                offers = []

            snap = {"Team": tname}
            for offer in offers:
                bname = offer["bookie_name"]
                snap[bname] = offer["current_odd"]

                try:
                    moves = _get_movements(driver, offer["offer_id"])
                    for move in moves:
                        history_rows.append({
                            "Datum":      move["t"],
                            "Team":       tname,
                            "Buchmacher": bname,
                            "Quote":      float(move["y"]),
                        })
                    print(f"    {bname}: {len(moves)} Datenpunkte")
                except Exception as e:
                    print(f"    WARNUNG Movements {bname}: {e}")

                time.sleep(0.3)  # kurze Pause zwischen Calls

            snapshot_rows.append(snap)
            time.sleep(0.5)

        print(f"  Gesamt: {len(history_rows)} Datenpunkte, {len(snapshot_rows)} Teams.")
        return history_rows, snapshot_rows

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        try:
            driver.service.process = None
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Datums-Snapshot
# ---------------------------------------------------------------------------

PRIORITY_BK = ["bet365", "Bwin", "Interwetten"]

def snapshot_at_date(history_rows: list[dict], target_date_str: str) -> pd.DataFrame:
    """
    Gibt einen Wide-Format-DataFrame zurück:
    Rows = Teams (nach Durchschnittsquote sortiert, Favoriten oben)
    Cols = Buchmacher (Priorität: bet365, Bwin, Interwetten, dann A-Z)
    Werte = letzte Quote vor/am Zieldatum
    Nur Teams, die am Zieldatum schon mindestens einen Datenpunkt hatten.
    """
    if not history_rows:
        return pd.DataFrame()

    df = pd.DataFrame(history_rows)
    df["Datum"] = pd.to_datetime(df["Datum"])
    target = pd.to_datetime(target_date_str)

    df_before = df[df["Datum"] <= target]
    if df_before.empty:
        return pd.DataFrame()

    # Für jedes Team×Buchmacher: letzter Wert vor/am Datum
    snap = (
        df_before
        .sort_values("Datum")
        .groupby(["Team", "Buchmacher"])["Quote"]
        .last()
        .unstack("Buchmacher")
        .reset_index()
    )

    # Spaltenreihenfolge: Priorität zuerst, dann Rest A-Z
    bk_cols = [c for c in snap.columns if c != "Team"]
    prio = [c for c in PRIORITY_BK if c in bk_cols]
    rest = sorted(c for c in bk_cols if c not in prio)
    snap = snap[["Team"] + prio + rest]

    # Nach Durchschnittsquote sortieren (Favoriten oben)
    num_cols = [c for c in snap.columns if c != "Team"]
    if num_cols:
        snap["_avg"] = snap[num_cols].mean(axis=1, skipna=True)
        snap = snap.sort_values("_avg").drop(columns="_avg")

    return snap.reset_index(drop=True)


def save_snapshot_excel(snap_df: pd.DataFrame, target_date_str: str, filepath: str | None = None) -> str:
    if not filepath:
        date_nodash = target_date_str.replace("-", "")
        filepath = f"wm2026_odds_snapshot_{date_nodash}_oddspedia.xlsx"

    sheet_name = f"Snapshot {target_date_str}"
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        snap_df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for col_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = min(width, 30)

    bk_cols = [c for c in snap_df.columns if c != "Team"]
    print(f"Gespeichert: {filepath}  ({len(snap_df)} Teams, {len(bk_cols)} Buchmacher)")
    return filepath


# ---------------------------------------------------------------------------
# Excel export (Full History)
# ---------------------------------------------------------------------------

def save_excel(history_rows: list[dict], snapshot_rows: list[dict], filepath: str | None = None) -> str:
    if not filepath:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"wm2026_odds_history_oddspedia_{ts}.xlsx"

    # --- Sheet 1: History (Long-Format) ---
    df_hist = pd.DataFrame(history_rows)
    if not df_hist.empty:
        df_hist["Datum"] = pd.to_datetime(df_hist["Datum"])
        df_hist = df_hist.sort_values(["Team", "Buchmacher", "Datum"]).reset_index(drop=True)

    # --- Sheet 2: Aktuell (Snapshot) ---
    df_snap = pd.DataFrame(snapshot_rows)
    if not df_snap.empty:
        bk_cols = [c for c in df_snap.columns if c != "Team"]
        for col in bk_cols:
            df_snap[col] = pd.to_numeric(df_snap[col], errors="coerce")
        if bk_cols:
            df_snap["_avg"] = df_snap[bk_cols].mean(axis=1, skipna=True)
            df_snap = df_snap.sort_values("_avg").drop(columns="_avg")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Sheet: History
        if not df_hist.empty:
            df_hist.to_excel(writer, index=False, sheet_name="History")
            ws = writer.sheets["History"]
            for col_cells in ws.columns:
                width = max(len(str(c.value or "")) for c in col_cells) + 2
                ws.column_dimensions[col_cells[0].column_letter].width = min(width, 30)

        # Sheet: Aktuell
        if not df_snap.empty:
            df_snap.to_excel(writer, index=False, sheet_name="Aktuell")
            ws = writer.sheets["Aktuell"]
            for col_cells in ws.columns:
                width = max(len(str(c.value or "")) for c in col_cells) + 2
                ws.column_dimensions[col_cells[0].column_letter].width = min(width, 25)

    bk_list = sorted(df_hist["Buchmacher"].unique().tolist()) if not df_hist.empty else []
    print(f"\n[4/4] Gespeichert: {filepath}")
    print(f"  History: {len(df_hist)} Zeilen | Teams: {df_hist['Team'].nunique() if not df_hist.empty else 0} | Buchmacher: {bk_list}")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(headless: bool = False, snapshot_date: str | None = None):
    history_rows, snapshot_rows = scrape(headless=headless)

    if not history_rows and not snapshot_rows:
        print("Keine Daten extrahiert.")
        return

    if snapshot_date:
        # Datums-Snapshot-Modus
        print(f"\n[4/4] Erstelle Snapshot für {snapshot_date} ...")
        snap_df = snapshot_at_date(history_rows, snapshot_date)

        if snap_df.empty:
            print(f"  Keine Daten vor/am {snapshot_date} gefunden.")
            return

        filepath = save_snapshot_excel(snap_df, snapshot_date)
        print(f"\nFertig! Datei: {filepath}")
        print(f"\nVorschau (Top 10):")
        bk_cols = [c for c in snap_df.columns if c != "Team"]
        print(snap_df.head(10)[["Team"] + bk_cols[:3]].to_string(index=False))

        # Hinweis auf fehlende Teams
        current_teams = {r["Team"] for r in snapshot_rows}
        snap_teams    = set(snap_df["Team"].tolist())
        missing = current_teams - snap_teams
        if missing:
            print(f"\nHinweis: {len(missing)} aktuelle Teams hatten am {snapshot_date} noch keine Quote:")
            print(f"  {sorted(missing)}")
        print(f"\nHinweis: Teams die nach dem {snapshot_date} aus dem Markt genommen wurden")
        print("  (z.B. nach Playoff-Ausscheiden) sind in dieser Datei NICHT enthalten –")
        print("  ihre Offers wurden von oddspedia deaktiviert und sind nicht mehr abrufbar.")
    else:
        # Standard-Modus: komplette History
        filepath = save_excel(history_rows, snapshot_rows)
        print(f"\nFertig! Datei: {filepath}")

        if history_rows:
            df = pd.DataFrame(history_rows)
            df["Datum"] = pd.to_datetime(df["Datum"])
            print("\nVorschau History (erste 10 Zeilen):")
            print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    args = sys.argv[1:]
    headless_arg  = "--headless" in args
    snapshot_arg  = None

    for i, a in enumerate(args):
        if a == "--snapshot" and i + 1 < len(args):
            snapshot_arg = args[i + 1]
            break
        if a.startswith("--snapshot="):
            snapshot_arg = a.split("=", 1)[1]
            break

    if snapshot_arg:
        try:
            datetime.strptime(snapshot_arg, "%Y-%m-%d")
        except ValueError:
            print(f"Fehler: Datum '{snapshot_arg}' muss im Format YYYY-MM-DD sein.")
            sys.exit(1)

    main(headless=headless_arg, snapshot_date=snapshot_arg)
