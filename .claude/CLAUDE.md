# CLAUDE.md – WM 2026 Predictions

## Projektüberblick

Dieses Projekt scraped Wettquoten von drei Quellen (Oddschecker, Oddspedia, Wettfreunde),
berechnet daraus Turniersieger-Wahrscheinlichkeiten (Basic Normalisation + Shin-Modell) und
stellt sie als interaktive HTML-Visualisierung sowie als PNG-Charts dar.

Datumsgrenzen: Vor WM-Start (< 11.06.2026) → `pre_wm`-Ordner; danach → `during_wm`-Ordner.
Die Umschaltung erfolgt automatisch über `wm_paths.py`.

---

## Häufige Befehle

```bash
# Vollständiger Daten-Update (Scrapen + Verarbeiten + PNG-Charts)
python run_all.py

# Wie oben, aber Browser unsichtbar im Hintergrund
python run_all.py --headless

# Nur processed_data_long/wide.xlsx aktualisieren (ohne Scraping)
python update_processed_data.py

# Interaktive HTML-Visualisierung neu bauen (wm2026_probabilities.html)
python create_visualization.py

# Nur PNG-Charts für README neu generieren
python visualization_png/create_png_charts.py

# Einzelscraper separat ausführen
python scraper_wettfreunde.py
python scraper_oddspedia.py [--headless]
python scraper_oddschecker.py
```

---

## Projektstruktur

```
run_all.py                      Einstiegspunkt: ruft alle 5 Schritte nacheinander auf
wm_paths.py                     Zentrale Pfadlogik (pre_wm ↔ during_wm, WM_START_DATE)
update_processed_data.py        Rohdaten → Long/Wide-Format + Shin-Berechnung
create_visualization.py         Baut wm2026_probabilities.html (Plotly, interaktiv)

scraper_oddschecker.py          Selenium-Scraper: Unibet, Ladbrokes, Betway, Betfair
scraper_oddspedia.py            undetected_chromedriver: bet365, Bwin (Cloudflare-Schutz)
scraper_wettfreunde.py          requests/BeautifulSoup: Interwetten

raw_data_pre_wm/                Rohdaten vor dem Turnier  (*.xlsx, DD.MM.YYYY im Namen)
raw_data_during_wm/             Rohdaten während des Turniers
processed_data_pre_wm/          processed_data_long.xlsx + processed_data_wide.xlsx
processed_data_during_wm/       wie oben, für die WM-Phase

visualization_png/
  create_png_charts.py          Balkendiagramm + Zeitverlauf-PNG für README
  flags/                        Flaggen-Icons für die Charts
  *.png                         Ausgabe-Charts

single_games_predictions/
  update_processed_single_odds.py   Einzelspiel-1X2-Prognosen verarbeiten
  raw_single_odds_during_wm.xlsx    Rohdaten Einzelspiele
  processed_match_predictions.xlsx  Ausgabe (wird von create_visualization.py geladen)

FAZ Material/                   Exportierte Excel-Dateien für FAZ-Artikel (manuell)
deprecated/                     Alte Skripte – nicht mehr verwenden
```

---

## Datenpipeline im Detail

```
scraper_*.py
  → raw_data_{pre/during}_wm/wm2026_{quelle}_DD.MM.YYYY.xlsx

update_processed_data.py
  → liest alle *.xlsx aus raw_dir()
  → gruppiert nach Datum im Dateinamen
  → führt Quellen zusammen (7 Zielbuchmacher: bet365, Bwin, Interwetten,
                              Unibet, Ladbrokes, Betway, Betfair)
  → berechnet Ø-Quote, Basic Normalisation, Shin-Wahrscheinlichkeit
  → schreibt processed_data_long.xlsx + processed_data_wide.xlsx

create_visualization.py
  → liest pre_wm-Long + during_wm-Long (kombinierte Zeitreihe)
  → liest optional single_games_predictions/processed_match_predictions.xlsx
  → schreibt wm2026_probabilities.html
```

---

## Konventionen

**Sprache:** Kommentare, Variablennamen, Spaltenbezeichnungen und Ausgaben sind auf **Deutsch**.
Dateinamen sind englisch/gemischt (historisch gewachsen).

**Type Hints:** Partiell vorhanden – neue Funktionen mit Type Hints versehen (wie in
`wm_paths.py` und `update_processed_data.py`). Nicht nachträglich in alte Funktionen
einbauen, wenn es keinen konkreten Nutzen gibt.

**Code-Stil:**
- `snake_case` für Funktionen und Variablen
- Konstanten in `UPPER_CASE`
- Spaltenbezeichnungen in DataFrames mit Unterstrichen, auf Deutsch
  (z. B. `Wahrscheinlichkeit_Shin_in_Prozent`)
- Dateiheader mit `# -*- coding: utf-8 -*-` und Docstring mit Verwendungshinweis
- Ausgaben mit `print()` statt `logging` (Skript-Charakter)

**Keine Tests:** Das Projekt hat keine automatisierten Tests. Qualitätsprüfung erfolgt
über die Datenkontrolle in `create_visualization.py` (Troubleshooting-Tab in der HTML).

---

## Wichtige Abhängigkeiten

| Paket                   | Zweck                                      |
|-------------------------|--------------------------------------------|
| `pandas`                | Datenverarbeitung, Excel lesen/schreiben   |
| `shin`                  | Shin-Modell zur Overround-Korrektur        |
| `selenium`              | Oddschecker-Scraper                        |
| `undetected_chromedriver` | Oddspedia-Scraper (Cloudflare-Bypass)    |
| `requests` + `bs4`      | Wettfreunde-Scraper                        |
| `plotly`                | Interaktive HTML-Visualisierung            |
| `matplotlib`            | PNG-Charts                                 |

Python-Version: **3.12**

---

## Phasen-Logik (`wm_paths.py`)

`WM_START_DATE = date(2026, 6, 11)` – dieses Datum steuert alles:

- `wm_paths.during_wm()` → `True` wenn `date.today() >= WM_START_DATE`
- `wm_paths.raw_dir()` → `raw_data_during_wm/` oder `raw_data_pre_wm/`
- `wm_paths.processed_long_file()` → entsprechend `processed_data_during_wm/processed_data_long.xlsx`

Die `pre_wm`-Daten bleiben immer erhalten und werden als historische Basis in der
Visualisierung mit den `during_wm`-Daten zusammengeführt.

---

## Teamname-Mapping

`update_processed_data.py` enthält `NAME_MAP` (Englisch → Deutsch) und `VALID_TEAMS`
(die 48 WM-Qualifizierten). Unbekannte Teams werden mit `[WARNUNG]` in der Konsole
angezeigt und verworfen. Neue Teams hier eintragen, falls sich Qualifizierungen ändern.

---

## Ausgeschiedene Teams in den Visualisierungen

### Balkendiagramm (PNG)

Ausgeschiedene Teams werden am unteren Ende des Balkendiagramms dargestellt:
gedimmte Flagge, rotes ×, grauer Balken, kursiver Austrittstext statt Prozentzahl.

Zwei Mechanismen greifen ineinander:

1. **Manuell** – `ELIMINATED`-Dict in `visualization_png/create_png_charts.py`:
   ```python
   ELIMINATED = {
       "Haiti":    "Gruppenphase",
       "Türkei":   "Gruppenphase",
       ...
   }
   ```
   Hier eintragen wenn ein Team ausscheidet. Mögliche Werte: `"Gruppenphase"`,
   `"Achtelfinale"`, `"Viertelfinale"`, `"Halbfinale"`, `"Finale"`.

2. **Automatisch** – Teams, die in during_wm-Daten vorkamen, im neuesten Snapshot
   aber fehlen (weil Buchmacher keine Quoten mehr zeigen), werden automatisch als
   ausgeschieden erkannt und als `"Gruppenphase"` beschriftet.

### Zeitverlauf-Liniendiagramm (PNG + HTML)

Das Ranking für Top 15 basiert auf dem **letzten verfügbaren Wert pro Team**
(`groupby("Team").last()`), nicht auf dem neuesten Gesamt-Snapshot. Dadurch bleiben
ausgeschiedene Teams im Diagramm sichtbar – ihre Linie endet einfach an dem Datum,
ab dem keine Quoten mehr vorlagen. Kein manuelles Eingreifen nötig.

- **PNG** (`build_line_chart`): Verbindungslinie von Datenpunkt zu Flagge startet
  beim letzten eigenen Datenpunkt des Teams (`team_last_date`), nicht beim globalen
  `last_date`.
- **HTML** (`rank_teams`): identische Logik mit `groupby().last()`.

---

## Typische Fehlerquellen

- **Selenium / ChromeDriver:** Muss zur installierten Chrome-Version passen.
  `undetected_chromedriver` lädt ggf. automatisch den passenden Driver.
- **Oddspedia-Scraper:** Cloudflare kann blockieren – bei Fehlern `--headless`
  weglassen oder manuell im Browser testen.
- **Excel-Dateien geöffnet:** Wenn eine `.xlsx` in Excel offen ist, erzeugt Windows
  eine `~$`-Sperrdatei. `update_processed_data.py` ignoriert diese bereits (`startswith("~$")`).
- **Datum im Dateinamen:** Rohdateien müssen das Muster `DD.MM.YYYY` im Namen tragen,
  sonst werden sie übersprungen (`[SKIP]`-Meldung in der Konsole).
