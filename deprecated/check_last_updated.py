"""
Oddspedia WM 2026 – Letzte Datenaktualisierung
Quelle: oddspedia.com/de/fussball/international/weltmeisterschaft/langzeitwetten

Prüft auf zwei Wegen, wann die Daten zuletzt aktualisiert wurden:
  1. HTTP-Response-Header (Last-Modified, Date) via Performance API
  2. Neuester Zeitstempel aus den Quoten-Bewegungen (getOutrightsMovements)

Verwendung:
    python check_last_updated.py
    python check_last_updated.py --headless
"""

import sys
import time
import json
from datetime import datetime, timezone

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL       = "https://oddspedia.com/de/fussball/international/weltmeisterschaft/langzeitwetten"
LEAGUE_ID = 3
WETTSTEUER = 0
GEO_CODE   = "DE"
LANGUAGE   = "de"
OT         = 1500


def _make_driver(headless: bool = False) -> uc.Chrome:
    opts = uc.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    if headless:
        opts.add_argument("--headless=new")
    return uc.Chrome(options=opts, version_main=147, headless=headless)


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


def _get_response_headers(driver) -> dict:
    """Liest Response-Header der Hauptseite über die Performance API aus."""
    entries = driver.execute_script("""
        var entries = performance.getEntriesByType('resource');
        var result = {};
        for (var e of entries) {
            if (e.name && e.name.includes('/api/v1/')) {
                result[e.name] = {
                    startTime: e.startTime,
                    duration: e.duration,
                    responseStart: e.responseStart
                };
            }
        }
        return result;
    """)
    return entries or {}


def _get_server_time_from_xhr(driver) -> str | None:
    """Liest den Date-Header aus einem frischen API-Call aus."""
    result = driver.execute_async_script("""
        var done = arguments[0];
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/v1/getOutrights?geoCode=DE&geoState=&leagueId=3&wettsteuer=0&ot=1500&handicap=&language=de', true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.onload = function() {
            done({
                date: xhr.getResponseHeader('date'),
                lastModified: xhr.getResponseHeader('last-modified'),
                cacheControl: xhr.getResponseHeader('cache-control'),
                age: xhr.getResponseHeader('age'),
                xCacheHit: xhr.getResponseHeader('x-cache'),
                responseText: this.responseText
            });
        };
        xhr.onerror = function() { done(null); };
        xhr.send();
    """)
    return result


def _get_all_offers(driver) -> list[dict]:
    """Holt alle Teams und ihre Offer-IDs."""
    data = _xhr(driver, _build_path(
        "getOutrights",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", language=LANGUAGE
    ))
    teams = []
    for entry in data.get("data", {}).get(str(OT), []):
        teams.append({
            "team_name": entry["team_name"],
            "team_id":   entry["team_id"],
        })
    return teams


def _get_offers_for_team(driver, team_id: int) -> list[dict]:
    path = _build_path(
        "getOutrightsSingle",
        geoCode=GEO_CODE, geoState="", leagueId=LEAGUE_ID,
        wettsteuer=WETTSTEUER, ot=OT, handicap="", teamId=team_id, language=LANGUAGE
    )
    data = _xhr(driver, path)
    return [
        {"offer_id": e["offer_id"], "bookie_name": e.get("bookie_name", "?")}
        for e in data.get("data", [])
        if e.get("offer_id")
    ]


def _get_latest_movement(driver, offer_id: int) -> datetime | None:
    """Gibt den neuesten Zeitstempel aus den Bewegungen eines Offers zurück."""
    path = _build_path(
        "getOutrightsMovements",
        leagueId=LEAGUE_ID, offerId=offer_id,
        wettsteuer=WETTSTEUER, language=LANGUAGE
    )
    try:
        data = _xhr(driver, path)
        moves = data.get("data", {}).get("moves", [])
        if not moves:
            return None
        timestamps = []
        for m in moves:
            try:
                timestamps.append(datetime.fromisoformat(m["t"].replace("Z", "+00:00")))
            except Exception:
                pass
        return max(timestamps) if timestamps else None
    except Exception:
        return None


def check_last_updated(headless: bool = False):
    print(f"Starte Browser und lade {URL} ...")
    driver = _make_driver(headless=headless)

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 40)

        # Cookie-Banner schließen
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

        # Tabelle abwarten
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".outrights-table-row")))
        except Exception:
            pass
        time.sleep(2)

        # ------------------------------------------------------------------
        # 1) HTTP-Header des API-Calls auslesen
        # ------------------------------------------------------------------
        print("\n[1/3] Prüfe HTTP-Response-Header ...")
        header_info = _get_server_time_from_xhr(driver)

        server_time    = None
        last_modified  = None
        cache_control  = None
        cache_age      = None
        x_cache        = None

        if header_info:
            date_str       = header_info.get("date")
            last_mod_str   = header_info.get("lastModified")
            cache_control  = header_info.get("cacheControl")
            cache_age      = header_info.get("age")
            x_cache        = header_info.get("xCacheHit")

            if date_str:
                try:
                    from email.utils import parsedate_to_datetime
                    server_time = parsedate_to_datetime(date_str)
                except Exception:
                    server_time = date_str

            if last_mod_str:
                try:
                    from email.utils import parsedate_to_datetime
                    last_modified = parsedate_to_datetime(last_mod_str)
                except Exception:
                    last_modified = last_mod_str

        # ------------------------------------------------------------------
        # 2) Neuester Zeitstempel aus Quoten-Bewegungen
        # ------------------------------------------------------------------
        print("[2/3] Lade Teams und Quoten-Offers ...")
        teams = _get_all_offers(driver)
        if not teams:
            print("  Keine Teams gefunden.")
            return

        print(f"  {len(teams)} Teams gefunden.")

        print("[3/3] Durchsuche Quoten-Bewegungen nach neuestem Zeitstempel ...")
        latest_overall: datetime | None = None
        latest_info = {"team": None, "bookie": None}

        # Nur die ersten N Teams prüfen – reicht für den neuesten Zeitstempel
        MAX_TEAMS = min(len(teams), 5)
        for i, team in enumerate(teams[:MAX_TEAMS]):
            tname = team["team_name"]
            tid   = team["team_id"]
            print(f"  [{i+1}/{MAX_TEAMS}] {tname}", end=" ", flush=True)

            try:
                offers = _get_offers_for_team(driver, tid)
            except Exception as e:
                print(f"  WARNUNG: {e}")
                continue

            team_latest: datetime | None = None
            team_latest_bookie = None

            for offer in offers:
                ts = _get_latest_movement(driver, offer["offer_id"])
                if ts and (team_latest is None or ts > team_latest):
                    team_latest       = ts
                    team_latest_bookie = offer["bookie_name"]
                time.sleep(0.2)

            if team_latest:
                print(f"→ {team_latest.strftime('%Y-%m-%d %H:%M:%S %Z')} ({team_latest_bookie})")
                if latest_overall is None or team_latest > latest_overall:
                    latest_overall         = team_latest
                    latest_info["team"]    = tname
                    latest_info["bookie"]  = team_latest_bookie
            else:
                print("→ kein Zeitstempel")

        # ------------------------------------------------------------------
        # Ausgabe
        # ------------------------------------------------------------------
        now_utc = datetime.now(timezone.utc)
        print("\n" + "=" * 60)
        print("  ERGEBNIS: Letzte Datenaktualisierung auf Oddspedia")
        print("=" * 60)

        print("\n--- HTTP-Header (API-Call) ---")
        if server_time:
            diff = now_utc - server_time if hasattr(server_time, "utcoffset") else None
            print(f"  Server-Zeit (Date):    {server_time}")
            if diff:
                print(f"  Alter des Responses:   {int(diff.total_seconds())} Sekunden")
        else:
            print("  Server-Zeit (Date):    nicht verfügbar")

        if last_modified:
            print(f"  Last-Modified:         {last_modified}")
        else:
            print("  Last-Modified:         nicht gesetzt (dynamische Seite)")

        if cache_control:
            print(f"  Cache-Control:         {cache_control}")
        if cache_age:
            print(f"  Cache-Age:             {cache_age} Sekunden")
        if x_cache:
            print(f"  X-Cache:               {x_cache}")

        print("\n--- Neuester Quoten-Zeitstempel (aus Bewegungsdaten) ---")
        if latest_overall:
            diff2 = now_utc - latest_overall if latest_overall.tzinfo else None
            print(f"  Neueste Bewegung:      {latest_overall.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  Team:                  {latest_info['team']}")
            print(f"  Buchmacher:            {latest_info['bookie']}")
            if diff2:
                mins  = int(diff2.total_seconds() // 60)
                hours = mins // 60
                days  = hours // 24
                if days > 0:
                    print(f"  Vor:                   {days} Tag(e) {hours % 24} Std. {mins % 60} Min.")
                elif hours > 0:
                    print(f"  Vor:                   {hours} Std. {mins % 60} Min.")
                else:
                    print(f"  Vor:                   {mins} Min.")
        else:
            print("  Neueste Bewegung:      nicht ermittelbar")

        print(f"\n  Aktueller Zeitpunkt:   {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        try:
            driver.service.process = None
        except Exception:
            pass


if __name__ == "__main__":
    args = sys.argv[1:]
    headless = "--headless" in args
    check_last_updated(headless=headless)
