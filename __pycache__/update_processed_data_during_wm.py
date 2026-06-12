# -*- coding: utf-8 -*-
"""
update_processed_data_during_wm.py

Liest die Rohdaten aus raw_data_during_wm/ (Oddschecker + Oddspedia),
führt sie pro Spiel/Ausgang zusammen und berechnet je Deutschland-Spiel:
  - Durchschnittliche Quote über alle verfügbaren Buchmacher
  - Wahrscheinlichkeit via Basic Normalisation
  - Wahrscheinlichkeit via Shin-Modell

Im Gegensatz zu update_processed_data.py gibt es hier KEINEN Zeitverlauf:
processed_data_during_wm/processed_match_predictions.xlsx wird bei jedem
Lauf komplett überschrieben (immer nur der aktuellste Snapshot).

Verwendung: python update_processed_data_during_wm.py
"""

import os
from datetime import datetime

import pandas as pd
import shin

from wm_matches_during import MATCHES, OUTCOMES

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE_DIR, "raw_data_during_wm")
OUT_DIR  = os.path.join(BASE_DIR, "processed_data_during_wm")
OUT_FILE = os.path.join(OUT_DIR, "processed_match_predictions.xlsx")

RAW_FILES = {
    "Oddschecker": os.path.join(RAW_DIR, "wm2026_oddschecker_during_wm.xlsx"),
    "Oddspedia":   os.path.join(RAW_DIR, "wm2026_oddspedia_during_wm.xlsx"),
}

META_COLS = ["Spiel_ID", "Heimteam", "Gastteam", "Datum", "Ausgang"]


# ---------------------------------------------------------------------------
# Rohdaten laden
# ---------------------------------------------------------------------------

def load_raw_files() -> pd.DataFrame | None:
    """Lädt und kombiniert die verfügbaren Rohdateien (Spiel_ID + Ausgang als Schlüssel)."""
    frames = []
    for source, filepath in RAW_FILES.items():
        if not os.path.exists(filepath):
            print(f"  [WARNUNG] {source}: Datei nicht gefunden ({filepath}) -> wird uebersprungen.")
            continue
        df = pd.read_excel(filepath)
        df.columns = df.columns.str.strip()
        frames.append(df)
        bk_cols = [c for c in df.columns if c not in META_COLS]
        print(f"  {source}: {len(df)} Zeilen, Buchmacher: {bk_cols}")

    if not frames:
        return None

    merged = frames[0]
    for df in frames[1:]:
        bk_cols = [c for c in df.columns if c not in META_COLS]
        merged = merged.merge(
            df[["Spiel_ID", "Ausgang"] + bk_cols],
            on=["Spiel_ID", "Ausgang"], how="outer",
        )

    return merged


# ---------------------------------------------------------------------------
# Berechnung
# ---------------------------------------------------------------------------

def process_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Berechnet je Deutschland-Spiel Durchschnittsquote sowie Basic- und Shin-Wahrscheinlichkeiten."""
    bk_cols = [c for c in df.columns if c not in META_COLS]
    for col in bk_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows = []

    for match in MATCHES:
        sub = df[df["Spiel_ID"] == match["id"]].set_index("Ausgang").reindex(OUTCOMES)

        num_odds = sub[bk_cols].where(sub[bk_cols] > 1)
        avg_odds = num_odds.mean(axis=1, skipna=True)
        n_bk     = num_odds.notna().sum(axis=1)

        if avg_odds.isna().any():
            missing = [o for o in OUTCOMES if pd.isna(avg_odds[o])]
            print(f"  [WARNUNG] {match['id']} ({match['heimteam']} - {match['gastteam']}): "
                  f"keine gueltigen Quoten fuer {missing} -> Spiel wird uebersprungen.")
            continue

        overround  = (1 / avg_odds).sum()
        prob_basic = (1 / avg_odds) / overround

        try:
            prob_shin = shin.calculate_implied_probabilities(avg_odds.tolist(), full_output=False)
        except Exception as e:
            print(f"  [WARNUNG] {match['id']}: Shin-Modell fehlgeschlagen ({e}) -> Spiel wird uebersprungen.")
            continue

        for i, outcome in enumerate(OUTCOMES):
            rows.append({
                "Spiel_ID":  match["id"],
                "Heimteam":  match["heimteam"],
                "Gastteam":  match["gastteam"],
                "Datum":     match["datum"],
                "Ausgang":   outcome,
                "Anzahl_Buchmacher":                  int(n_bk[outcome]),
                "Durchsch_Quote":                     round(avg_odds[outcome], 4),
                "Wahrscheinlichkeit_in_Prozent":      round(prob_basic[outcome] * 100, 4),
                "Wahrscheinlichkeit_Shin_in_Prozent": round(prob_shin[i] * 100, 4),
                "Letzte_Aktualisierung":              now,
            })

        print(f"  {match['id']}: {match['heimteam']} - {match['gastteam']}  "
              f"| Norm-Summe: {prob_basic.sum():.4f}  | Shin-Summe: {sum(prob_shin):.4f}")

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  update_processed_data_during_wm.py")
    print("=" * 60)
    print()

    df = load_raw_files()
    if df is None:
        print("\nKeine Rohdaten in raw_data_during_wm/ gefunden - nichts zu tun.")
        return

    print()
    df_result = process_matches(df)

    if df_result.empty:
        print("\nKeine verwertbaren Daten - processed_match_predictions.xlsx wird nicht geschrieben.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    df_result.to_excel(OUT_FILE, index=False)
    print(f"\nGespeichert: {OUT_FILE}  ({len(df_result)} Zeilen)")

    print("\nVorschau:")
    print(df_result[[
        "Spiel_ID", "Ausgang", "Anzahl_Buchmacher", "Durchsch_Quote",
        "Wahrscheinlichkeit_in_Prozent", "Wahrscheinlichkeit_Shin_in_Prozent",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
