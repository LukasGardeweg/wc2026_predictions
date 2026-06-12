# -*- coding: utf-8 -*-
"""
wm_matches_during.py

Zentrale Konfiguration der Deutschland-Spiele für die "Während der WM"-Analysen
(Einzelspiel-1X2-Prognosen). Wird von den Scrapern, der Verarbeitung und der
Visualisierung importiert.

Heimteam/Gastteam = Reihenfolge, wie Oddschecker das Spiel listet (Zeile 1 = Heim).
"Heimsieg"/"Heimniederlage" beziehen sich auf dieses Team, nicht zwingend auf
Deutschland.

Hinweis: Die Oddschecker-URLs für Spiel 2 (Elfenbeinküste) und Spiel 3 (Ecuador)
sind ein Best-Guess und müssen beim ersten echten Lauf verifiziert/korrigiert
werden.
"""

MATCHES = [
    {
        "id":               "deu_cuw",
        "heimteam":         "Deutschland",
        "gastteam":         "Curaçao",
        "heimteam_en":      "Germany",
        "gastteam_en":      "Curacao",
        "datum":            "14.06.2026",
        "oddschecker_url":  "https://www.oddschecker.com/football/world-cup/germany-v-curacao/winner",
        "oddspedia_event_id": 1654561,
        "oddspedia_slug":   "germany-curacao",
    },
    {
        "id":               "civ_deu",
        "heimteam":         "Elfenbeinküste",
        "gastteam":         "Deutschland",
        "heimteam_en":      "Ivory Coast",
        "gastteam_en":      "Germany",
        "datum":            "20.06.2026",
        "oddschecker_url":  "https://www.oddschecker.com/football/world-cup/ivory-coast-v-germany/winner",
        "oddspedia_event_id": 1654563,
        "oddspedia_slug":   "ivory-coast-germany",
    },
    {
        "id":               "ecu_deu",
        "heimteam":         "Ecuador",
        "gastteam":         "Deutschland",
        "heimteam_en":      "Ecuador",
        "gastteam_en":      "Germany",
        "datum":            "24.06.2026",
        "oddschecker_url":  "https://www.oddschecker.com/football/world-cup/ecuador-v-germany/winner",
        "oddspedia_event_id": 1654565,
        "oddspedia_slug":   "ecuador-germany",
    },
]

# Mögliche Bezeichnungen für die drei Marktausgänge
OUTCOMES = ["Heimsieg", "Unentschieden", "Heimniederlage"]
