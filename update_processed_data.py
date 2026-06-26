# -*- coding: utf-8 -*-
"""
update_processed_data.py

Liest alle Rohdaten aus raw_data_pre_wm/ bzw. (ab WM-Start) raw_data_during_wm/,
gruppiert sie nach Datum, führt pro Datum alle Quellen zusammen und berechnet:
  - Durchschnittliche Quote über die 7 Zielbuchmacher
  - Wahrscheinlichkeit via Basic Normalisation
  - Wahrscheinlichkeit via Shin-Modell

Regeln:
  - Neue Daten (Datum noch nicht in processed_data_long) -> anhängen
  - Datum bereits vorhanden, aber jetzt MEHR Buchmacher verfügbar -> neu berechnen
  - Datum bereits vorhanden mit gleicher oder niedrigerer Buchmachers-Anzahl -> unverändert
  - Daten ohne zugehörige Rohdateien (manuell eingetragen) -> nie angetastet

Pfade (Roh- und Verarbeitungsordner) werden über wm_paths.py automatisch
anhand des heutigen Datums gewählt: vor dem WM-Start (11.06.2026) pre_wm,
ab dann during_wm.

Verwendung: python update_processed_data.py
"""

import os
import re

import pandas as pd
import shin

import wm_paths

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE             = os.path.dirname(os.path.abspath(__file__))
RAW_DIR          = wm_paths.raw_dir()
PROCESSED_FILE   = wm_paths.processed_long_file()
WIDE_FILE        = wm_paths.processed_wide_file()
PRE_WM_LONG_FILE = os.path.join(BASE, "processed_data_pre_wm", "processed_data_long.xlsx")

# Spalten des Long-Formats (für eine leere/neue processed_data_long.xlsx)
LONG_COLUMNS = [
    "Team", "Datum", "Anzahl_Buchmacher", "Durchsch_Quote",
    "Wahrscheinlichkeit", "Wahrscheinlichkeit_in_Prozent",
    "Wahrscheinlichkeit_Shin", "Wahrscheinlichkeit_Shin_in_Prozent",
]

# ---------------------------------------------------------------------------
# Die 7 Zielbuchmacher (exakte Spaltennamen in den Rohdateien)
# ---------------------------------------------------------------------------
TARGET_BOOKMAKERS = {"bet365", "Bwin", "Interwetten", "Unibet", "Ladbrokes", "Betway", "Betfair"}

# ---------------------------------------------------------------------------
# Teamname-Mapping  (Englisch -> Deutsch  +  Deutsche Varianten)
# ---------------------------------------------------------------------------
NAME_MAP = {
    # Englisch -> Deutsch (Oddschecker)
    "Algeria":                 "Algerien",
    "Argentina":               "Argentinien",
    "Australia":               "Australien",
    "Austria":                 "Österreich",
    "Belgium":                 "Belgien",
    "Bosnia and Herzegovina":  "Bosnien Herzegowina",
    "Brazil":                  "Brasilien",
    "Canada":                  "Kanada",
    "Cape Verde":              "Kap Verde",
    "Colombia":                "Kolumbien",
    "Croatia":                 "Kroatien",
    "Curacao":                 "Curacao",
    "Czech Republic":          "Tschechien",
    "DR Congo":                "DR Kongo",
    "Ecuador":                 "Ecuador",
    "Egypt":                   "Ägypten",
    "England":                 "England",
    "France":                  "Frankreich",
    "Germany":                 "Deutschland",
    "Ghana":                   "Ghana",
    "Haiti":                   "Haiti",
    "Iran":                    "Iran",
    "Iraq":                    "Irak",
    "Ivory Coast":             "Elfenbeinküste",
    "Japan":                   "Japan",
    "Jordan":                  "Jordanien",
    "Mexico":                  "Mexiko",
    "Morocco":                 "Marokko",
    "Netherlands":             "Niederlande",
    "New Zealand":             "Neuseeland",
    "Norway":                  "Norwegen",
    "Panama":                  "Panama",
    "Paraguay":                "Paraguay",
    "Portugal":                "Portugal",
    "Qatar":                   "Katar",
    "Saudi Arabia":            "Saudi Arabien",
    "Scotland":                "Schottland",
    "Senegal":                 "Senegal",
    "South Africa":            "Südafrika",
    "South Korea":             "Südkorea",
    "Spain":                   "Spanien",
    "Sweden":                  "Schweden",
    "Switzerland":             "Schweiz",
    "Tunisia":                 "Tunesien",
    "Turkey":                  "Türkei",
    "USA":                     "USA",
    "Uruguay":                 "Uruguay",
    "Uzbekistan":              "Usbekistan",
    # Deutsche Varianten (Wettfreunde vs. Oddspedia)
    "Bosnien und Herzegowina": "Bosnien Herzegowina",
    "Bosnien":                 "Bosnien Herzegowina",
    "Saudi-Arabien":           "Saudi Arabien",
}

# ---------------------------------------------------------------------------
# Die 48 Teams des WM-2026-Felds (kanonische deutsche Namen, nach NAME_MAP)
# Zeilen für andere Teams (z. B. zusätzliche Oddschecker-Marktwetten auf
# nicht qualifizierte Teams) werden in load_raw_file() verworfen.
# ---------------------------------------------------------------------------
VALID_TEAMS = {
    "Algerien", "Argentinien", "Australien", "Belgien", "Bosnien Herzegowina",
    "Brasilien", "Curacao", "DR Kongo", "Deutschland", "Ecuador",
    "Elfenbeinküste", "England", "Frankreich", "Ghana", "Haiti", "Irak",
    "Iran", "Japan", "Jordanien", "Kanada", "Kap Verde", "Katar", "Kolumbien",
    "Kroatien", "Marokko", "Mexiko", "Neuseeland", "Niederlande", "Norwegen",
    "Panama", "Paraguay", "Portugal", "Saudi Arabien", "Schottland",
    "Schweden", "Schweiz", "Senegal", "Spanien", "Südafrika", "Südkorea",
    "Tschechien", "Tunesien", "Türkei", "USA", "Uruguay", "Usbekistan",
    "Ägypten", "Österreich",
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def extract_date(filename: str) -> pd.Timestamp | None:
    """Extrahiert Datum aus Dateinamen der Form *DD.MM.YYYY.xlsx"""
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", filename)
    if m:
        day, month, year = m.groups()
        return pd.Timestamp(f"{year}-{month}-{day}")
    return None


def load_raw_file(filepath: str) -> pd.DataFrame:
    """
    Liest eine Rohdatei, normalisiert Teamnamen und gibt nur
    die vorhandenen Zielbuchmacher-Spalten zurück.
    """
    df = pd.read_excel(filepath)
    df.columns = df.columns.str.strip()
    df["Team"] = df["Team"].astype(str).str.strip().map(lambda x: NAME_MAP.get(x, x))

    unknown = sorted(set(df["Team"]) - VALID_TEAMS)
    if unknown:
        print(f"    [WARNUNG] Unbekannte Teams ignoriert: {unknown}")
    df = df[df["Team"].isin(VALID_TEAMS)]

    bk_cols = [c for c in df.columns if c != "Team" and c in TARGET_BOOKMAKERS]
    result  = df[["Team"] + bk_cols].copy()
    for col in bk_cols:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


def count_bookmakers(filenames: list[str]) -> int:
    """Zählt die verfügbaren Zielbuchmacher über alle Dateien eines Datums."""
    bk_found = set()
    for fn in filenames:
        df = load_raw_file(os.path.join(RAW_DIR, fn))
        bk_found.update(c for c in df.columns if c != "Team")
    return len(bk_found)


def process_date(date_key: pd.Timestamp, filenames: list[str]) -> pd.DataFrame:
    """
    Führt alle Rohdateien eines Datums zusammen und berechnet
    Durchschnittsquote, Basic Normalisation und Shin-Wahrscheinlichkeit.
    Gibt einen DataFrame mit einer zusätzlichen Spalte Anzahl_Buchmacher zurück.
    """
    merged  = None
    bk_used = set()

    for filename in sorted(filenames):
        filepath = os.path.join(RAW_DIR, filename)
        df_raw   = load_raw_file(filepath)
        bk_cols  = [c for c in df_raw.columns if c != "Team"]
        bk_used.update(bk_cols)
        print(f"    {filename}  ->  {bk_cols}")

        if merged is None:
            merged = df_raw
        else:
            merged = merged.merge(df_raw, on="Team", how="outer")
            # Buchmacher der in mehreren Quellen vorkommt -> _x/_y zusammenführen
            for bk in list(TARGET_BOOKMAKERS):
                col_x, col_y = f"{bk}_x", f"{bk}_y"
                if col_x in merged.columns and col_y in merged.columns:
                    merged[bk] = merged[[col_x, col_y]].mean(axis=1, skipna=True)
                    merged = merged.drop(columns=[col_x, col_y])

    # Durchschnitt über alle verfügbaren Zielbuchmacher
    # Einzelquoten <= 1 (z. B. 0 = nicht angeboten) werden als fehlend behandelt
    avg_cols  = [c for c in merged.columns if c != "Team"]
    num_odds  = merged[avg_cols].apply(pd.to_numeric, errors="coerce")
    num_odds  = num_odds.where(num_odds > 1)   # 0 / ungültige Werte -> NaN
    avg_odds  = num_odds.mean(axis=1, skipna=True)

    # Teams ohne gültige Quote verwerfen
    valid    = avg_odds.notna() & (avg_odds > 1)
    merged   = merged[valid].reset_index(drop=True)
    avg_odds = avg_odds[valid].reset_index(drop=True)

    # Basic Normalisation
    overround  = (1 / avg_odds).sum()
    prob_basic = (1 / avg_odds) / overround

    # Shin-Modell
    prob_shin = shin.calculate_implied_probabilities(avg_odds.tolist(), full_output=False)

    n_bk = len(bk_used)
    print(f"    {len(merged)} Teams | {n_bk} Buchmacher: {sorted(bk_used)} | Shin-Summe: {sum(prob_shin):.4f}")

    return pd.DataFrame({
        "Team":                               merged["Team"].values,
        "Datum":                              date_key,
        "Anzahl_Buchmacher":                  n_bk,
        "Durchsch_Quote":                     avg_odds.round(4).values,
        "Wahrscheinlichkeit":                 prob_basic.round(6).values,
        "Wahrscheinlichkeit_in_Prozent":      (prob_basic * 100).round(4).values,
        "Wahrscheinlichkeit_Shin":            [round(p, 6) for p in prob_shin],
        "Wahrscheinlichkeit_Shin_in_Prozent": [round(p * 100, 4) for p in prob_shin],
    })


# ---------------------------------------------------------------------------
# Wide-Format
# ---------------------------------------------------------------------------

def build_wide_format(df_long: pd.DataFrame) -> pd.DataFrame:
    """
    Erzeugt das Wide-Format aus dem Long-Format.

    Struktur: Team | Datum_1 | Durchsch_Quote_1 | Norm_Wahrscheinlichkeit_in_Prozent_1
                   | Shin_Wahrscheinlichkeit_in_Prozent_1 | Datum_2 | ...
    Sortierung: Teams nach neuestem Snapshot (Shin) absteigend.
    """
    df = df_long.copy()
    df["Datum"] = pd.to_datetime(df["Datum"])

    snapshots = sorted(df["Datum"].unique())
    if not snapshots:
        return pd.DataFrame({"Team": []})

    teams = (
        df[df["Datum"] == snapshots[-1]]
        .sort_values("Wahrscheinlichkeit_Shin", ascending=False)["Team"]
        .tolist()
    )

    result = pd.DataFrame({"Team": teams})

    for i, datum in enumerate(snapshots, start=1):
        snap = df[df["Datum"] == datum].set_index("Team")
        result[f"Datum_{i}"]                              = datum.strftime("%d.%m.%Y")
        result[f"Durchsch_Quote_{i}"]                     = result["Team"].map(snap["Durchsch_Quote"]).round(2)
        result[f"Norm_Wahrscheinlichkeit_in_Prozent_{i}"] = result["Team"].map(snap["Wahrscheinlichkeit_in_Prozent"]).round(2)
        result[f"Shin_Wahrscheinlichkeit_in_Prozent_{i}"] = result["Team"].map(snap["Wahrscheinlichkeit_Shin_in_Prozent"]).round(2)

    return result


def save_wide_format(df_long: pd.DataFrame) -> None:
    """Baut Wide-Format und speichert es als Excel."""
    df_wide = build_wide_format(df_long)
    df_wide.to_excel(WIDE_FILE, index=False)
    if df_wide.empty:
        print(f"Wide-Format: noch keine Daten  ->  {WIDE_FILE}")
    else:
        snapshots = (len(df_wide.columns) - 1) // 4  # 4 Spalten pro Zeitpunkt
        print(f"Wide-Format: {len(df_wide)} Teams x {snapshots} Zeitpunkte  ->  {WIDE_FILE}")


# ---------------------------------------------------------------------------
# Fehlende Teams in Snapshots auffüllen (during_wm-Phase)
# ---------------------------------------------------------------------------

def get_all_known_teams(df_existing: pd.DataFrame) -> set[str]:
    """
    Gibt alle Teams zurück, die je in pre_wm oder during_wm vorkamen.
    Damit werden ausgeschiedene Teams identifiziert, für die NaN-Zeilen
    in neuen Snapshots angelegt werden müssen.
    """
    teams: set[str] = set(df_existing["Team"].dropna()) if not df_existing.empty else set()
    if os.path.exists(PRE_WM_LONG_FILE):
        df_pre = load_existing(PRE_WM_LONG_FILE)
        teams |= set(df_pre["Team"].dropna())
    return teams


def pad_missing_teams(
    df_new: pd.DataFrame, all_teams: set[str], date_key: pd.Timestamp
) -> pd.DataFrame:
    """
    Fügt für jedes bekannte Team, das im aktuellen Snapshot fehlt, eine Zeile
    mit NaN-Werten ein. Dadurch bleiben ausgeschiedene Teams im Long-Format
    sichtbar – die leeren Zellen signalisieren „keine Quoten verfügbar".
    """
    present = set(df_new["Team"])
    missing = all_teams - present
    if not missing:
        return df_new
    nan_rows = pd.DataFrame({
        "Team":                               sorted(missing),
        "Datum":                              date_key,
        "Anzahl_Buchmacher":                  pd.NA,
        "Durchsch_Quote":                     pd.NA,
        "Wahrscheinlichkeit":                 pd.NA,
        "Wahrscheinlichkeit_in_Prozent":      pd.NA,
        "Wahrscheinlichkeit_Shin":            pd.NA,
        "Wahrscheinlichkeit_Shin_in_Prozent": pd.NA,
    })
    return pd.concat([df_new, nan_rows], ignore_index=True)


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------

def load_existing(path: str) -> pd.DataFrame:
    """
    Lädt processed_data_long.xlsx. Falls die Datei noch nicht existiert oder
    nur ein leerer Platzhalter ist (z.B. frisch angelegter during_wm-Ordner
    vor dem ersten Lauf), wird ein leerer DataFrame mit den Long-Spalten
    zurückgegeben.
    """
    if os.path.exists(path):
        df = pd.read_excel(path)
        if not df.empty and not df.columns.empty:
            df.columns = df.columns.astype(str).str.strip()
        if "Team" in df.columns and "Datum" in df.columns:
            df["Datum"] = pd.to_datetime(df["Datum"])
            df["Team"]  = df["Team"].astype(str).str.strip()
            if "Anzahl_Buchmacher" not in df.columns:
                df["Anzahl_Buchmacher"] = pd.NA
            return df

    df = pd.DataFrame(columns=LONG_COLUMNS)
    df["Datum"] = pd.to_datetime(df["Datum"])
    return df


def main():
    # Bestehende Daten laden
    df_existing = load_existing(PROCESSED_FILE)

    # Fehlende Team-Zeilen in bestehenden Snapshots reparieren (nur during_wm)
    repaired_count = 0
    if wm_paths.during_wm():
        all_known_teams = get_all_known_teams(df_existing)
        if all_known_teams and not df_existing.empty:
            repair_rows = []
            for date_rep, grp in df_existing.groupby("Datum"):
                missing = all_known_teams - set(grp["Team"])
                for team in sorted(missing):
                    repair_rows.append({
                        "Team": team, "Datum": date_rep,
                        "Anzahl_Buchmacher": pd.NA, "Durchsch_Quote": pd.NA,
                        "Wahrscheinlichkeit": pd.NA, "Wahrscheinlichkeit_in_Prozent": pd.NA,
                        "Wahrscheinlichkeit_Shin": pd.NA, "Wahrscheinlichkeit_Shin_in_Prozent": pd.NA,
                    })
            if repair_rows:
                df_existing = pd.concat(
                    [df_existing, pd.DataFrame(repair_rows)], ignore_index=True
                )
                df_existing = df_existing.sort_values(
                    ["Datum", "Wahrscheinlichkeit_Shin"],
                    ascending=[True, False],
                    na_position="last",
                ).reset_index(drop=True)
                repaired_count = len(repair_rows)
    else:
        all_known_teams = set()

    existing_dates = set(df_existing["Datum"].dt.normalize().unique())

    print("=" * 60)
    print("  update_processed_data.py")
    print("=" * 60)
    if repaired_count:
        print(f"\n  [REPARIERT] {repaired_count} fehlende Team-Zeilen für bestehende Snapshots ergänzt.")
    print(f"\nBestehende Snapshots ({len(existing_dates)}):")
    print(f"  {sorted(d.date() for d in existing_dates)}")

    # Alle Rohdateien nach Datum gruppieren
    files_by_date: dict[pd.Timestamp, list[str]] = {}
    for filename in sorted(os.listdir(RAW_DIR)):
        if not filename.endswith(".xlsx") or filename.startswith("~$"):
            continue
        datum = extract_date(filename)
        if datum is None:
            print(f"\n  [SKIP] Kein Datum erkannt: {filename}")
            continue
        files_by_date.setdefault(datum.normalize(), []).append(filename)

    # Neue und aktualisierbare Daten verarbeiten
    new_dfs     = []
    dates_to_update = []
    print()

    for date_key in sorted(files_by_date):
        filenames = files_by_date[date_key]

        if date_key not in existing_dates:
            # Neues Datum -> verarbeiten
            print(f"  [NEU]        {date_key.date()}  ({len(filenames)} Datei(en)):")
            df_new = process_date(date_key, filenames)
            if wm_paths.during_wm() and all_known_teams:
                df_new = pad_missing_teams(df_new, all_known_teams, date_key)
            new_dfs.append(df_new)
            continue

        # Datum vorhanden -> prüfen ob mehr Buchmacher verfügbar
        stored_bk = df_existing.loc[
            df_existing["Datum"].dt.normalize() == date_key, "Anzahl_Buchmacher"
        ].iloc[0]

        if pd.isna(stored_bk):
            # Manuell eingetragene Daten ohne Tracking -> nie anfassen
            print(f"  [MANUELL]    {date_key.date()}  ->  unveraendert (keine Rohdaten-Herkunft)")
            continue

        available_bk = count_bookmakers(filenames)

        if available_bk <= int(stored_bk):
            print(f"  [VORHANDEN]  {date_key.date()}  ({int(stored_bk)} BK gespeichert, {available_bk} verfuegbar)")
            continue

        # Mehr Buchmacher -> neu berechnen
        print(f"  [UPDATE]     {date_key.date()}  ({int(stored_bk)} BK -> {available_bk} BK):")
        dates_to_update.append(date_key)
        df_new = process_date(date_key, filenames)
        if wm_paths.during_wm() and all_known_teams:
            df_new = pad_missing_teams(df_new, all_known_teams, date_key)
        new_dfs.append(df_new)

    print()

    if not new_dfs:
        if repaired_count:
            df_existing.to_excel(PROCESSED_FILE, index=False)
            print(f"Reparierte Daten gespeichert  ->  {PROCESSED_FILE}")
        else:
            print("Keine neuen oder aktualisierten Daten. processed_data_long.xlsx bleibt unveraendert.")
        print()
        save_wide_format(df_existing)
        return

    # Zeilen der zu aktualisierenden Daten entfernen
    if dates_to_update:
        mask = df_existing["Datum"].dt.normalize().isin(dates_to_update)
        df_existing = df_existing[~mask]
        print(f"  {mask.sum()} veraltete Zeilen ersetzt.")

    # Neue/aktualisierte Daten anhängen
    df_updated = pd.concat([d for d in [df_existing] + new_dfs if not d.empty], ignore_index=True)
    df_updated = df_updated.sort_values(
        ["Datum", "Wahrscheinlichkeit_Shin"],
        ascending=[True, False],
        na_position="last",
    ).reset_index(drop=True)

    df_updated.to_excel(PROCESSED_FILE, index=False)

    added = sum(len(d) for d in new_dfs)
    print(f"Fertig!  +{added} Zeilen hinzugefuegt/aktualisiert  ->  gesamt {len(df_updated)} Zeilen")
    print(f"Long:    {PROCESSED_FILE}")
    print()
    save_wide_format(df_updated)

    # Vorschau neuester Snapshot
    latest_date = max(df["Datum"].iloc[0] for df in new_dfs)
    preview = pd.concat(new_dfs)
    preview = preview[preview["Datum"] == latest_date].sort_values(
        "Wahrscheinlichkeit_Shin_in_Prozent", ascending=False
    )
    print(f"\nTop 10 ({latest_date.date()}):")
    print(preview.head(10)[[
        "Team", "Anzahl_Buchmacher", "Durchsch_Quote",
        "Wahrscheinlichkeit_in_Prozent",
        "Wahrscheinlichkeit_Shin_in_Prozent"
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
