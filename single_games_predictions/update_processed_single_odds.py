# -*- coding: utf-8 -*-
"""
update_processed_single_odds.py

Liest Einzelspielprognosen/raw_single_odds_during_wm.xlsx (manuell eingetragene
1X2-Quoten der Deutschland-Spiele während der WM) und berechnet pro Spiel:
  - Durchschnittliche Quote über die Buchmacher, die für dieses Spiel
    vollständige 1X2-Quoten eingetragen haben
  - Wahrscheinlichkeit via Basic Normalisation
  - Wahrscheinlichkeit via Shin-Modell

Zeilen, in denen noch keine Quoten eingetragen wurden, werden übersprungen.

Verwendung: python update_processed_single_odds.py
"""

import os
from datetime import datetime

import pandas as pd
import shin

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
BASE     = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(BASE, "raw_single_odds_during_wm.xlsx")
OUT_FILE = os.path.join(BASE, "processed_match_predictions.xlsx")

# ---------------------------------------------------------------------------
# Buchmacher-Spaltenpräfixe in der Rohdatei
# ---------------------------------------------------------------------------
BOOKMAKER_PREFIXES = ["bet365", "bwin", "iw", "ub", "lb", "bw", "bf"]

OUTCOMES   = ["Heimsieg", "Unentschieden", "Heimniederlage"]
SUFFIXES   = ["home", "draw", "away"]


def main():
    df = pd.read_excel(RAW_FILE, sheet_name="Oddspedia 1X2")
    df.columns = df.columns.str.strip()

    today = datetime.now().strftime("%d.%m.%Y")
    rows  = []

    for _, row in df.iterrows():
        spiel_id = row.get("Spiel_ID")
        if pd.isna(spiel_id):
            continue

        # Pro Buchmacher prüfen, ob vollständige 1X2-Quoten eingetragen wurden
        odds_per_outcome = {s: [] for s in SUFFIXES}
        n_bk = 0
        for prefix in BOOKMAKER_PREFIXES:
            vals = [pd.to_numeric(row.get(f"{prefix}_{s}"), errors="coerce") for s in SUFFIXES]
            if all(v > 1 for v in vals):
                n_bk += 1
                for s, v in zip(SUFFIXES, vals):
                    odds_per_outcome[s].append(v)

        if n_bk == 0:
            print(f"  [SKIP] {spiel_id} – noch keine Quoten eingetragen")
            continue

        avg_odds  = {s: sum(vals) / len(vals) for s, vals in odds_per_outcome.items()}
        odds_list = [avg_odds[s] for s in SUFFIXES]

        overround  = sum(1 / o for o in odds_list)
        prob_basic = [(1 / o) / overround for o in odds_list]
        prob_shin  = shin.calculate_implied_probabilities(odds_list, full_output=False)

        print(f"  [OK]   {spiel_id}  ->  {n_bk} Buchmacher  |  Quoten: "
              f"{avg_odds['home']:.2f} / {avg_odds['draw']:.2f} / {avg_odds['away']:.2f}")

        for outcome, suffix, p_basic, p_shin in zip(OUTCOMES, SUFFIXES, prob_basic, prob_shin):
            rows.append({
                "Spiel_ID":                          spiel_id,
                "Heimteam":                          row["Heimteam"],
                "Gastteam":                          row["Gastteam"],
                "Datum":                             row["Datum"],
                "Ausgang":                           outcome,
                "Anzahl_Buchmacher":                 n_bk,
                "Durchsch_Quote":                    round(avg_odds[suffix], 4),
                "Wahrscheinlichkeit":                round(p_basic, 6),
                "Wahrscheinlichkeit_in_Prozent":      round(p_basic * 100, 4),
                "Wahrscheinlichkeit_Shin":            round(p_shin, 6),
                "Wahrscheinlichkeit_Shin_in_Prozent": round(p_shin * 100, 4),
                "Letzte_Aktualisierung":             today,
            })

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    df_out = pd.DataFrame(rows)
    df_out.to_excel(OUT_FILE, index=False)

    if df_out.empty:
        print(f"\nKeine Spiele mit eingetragenen Quoten gefunden -> {OUT_FILE} (leer)")
    else:
        print(f"\nFertig -> {OUT_FILE}  ({df_out['Spiel_ID'].nunique()} Spiel(e))")


if __name__ == "__main__":
    main()
