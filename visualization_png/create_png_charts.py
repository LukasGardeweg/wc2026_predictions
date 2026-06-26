# -*- coding: utf-8 -*-
"""
create_png_charts.py
Erzeugt zwei publikationsreife PNG-Grafiken aus der durchgehenden
Zeitreihe der Shin-Wahrscheinlichkeiten (pre_wm + during_wm):

  1. Balkendiagramm: Shin-Wahrscheinlichkeiten aller 48 Teams (neuester Snapshot)
     Ausgeschiedene Teams erscheinen ganz unten – gedimmt, mit rotem ×,
     ohne Prozentzahl, dafür mit dem Austrittstext (z. B. "Ausgeschieden · Gruppenphase").
  2. Zeitverlauf: Top 15 Teams (Shin-Wahrscheinlichkeit) über die Zeit

Beide Grafiken sind mit den jeweiligen Landesflaggen beschriftet und werden
bei jedem Lauf mit dem jeweils neuesten Snapshot überschrieben, sodass sie
parallel zum Turnierverlauf aktuell bleiben (siehe README.md).

Verwendung: python create_png_charts.py
"""

import os
import sys
import urllib.request

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

BASE                = os.path.dirname(os.path.abspath(__file__))
ROOT                = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import wm_paths
PRE_WM_LONG_FILE    = os.path.join(ROOT, "processed_data_pre_wm",    "processed_data_long.xlsx")
DURING_WM_LONG_FILE = os.path.join(ROOT, "processed_data_during_wm", "processed_data_long.xlsx")
FLAG_DIR            = os.path.join(BASE, "flags")
BAR_OUTPUT          = os.path.join(BASE, "wm2026_balkendiagramm_alle_teams.png")
LINE_OUTPUT         = os.path.join(BASE, "wm2026_zeitverlauf_top15.png")

COLORS = [
    "#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#F4A261",
    "#264653", "#6D6875", "#B5838D", "#CC0000", "#80B918",
    "#3A0CA3", "#F72585", "#009999", "#7B2D8B", "#FF6B35",
]

# Deutsche Teamnamen -> ISO/flagcdn-Ländercode
FLAG_CODES = {
    "Spanien": "es", "Frankreich": "fr", "England": "gb-eng", "Portugal": "pt",
    "Brasilien": "br", "Argentinien": "ar", "Deutschland": "de", "Niederlande": "nl",
    "Norwegen": "no", "Belgien": "be", "Kolumbien": "co", "Marokko": "ma",
    "Japan": "jp", "USA": "us", "Mexiko": "mx", "Uruguay": "uy",
    "Schweiz": "ch", "Türkei": "tr", "Kroatien": "hr", "Ecuador": "ec",
    "Senegal": "sn", "Schweden": "se", "Österreich": "at", "Kanada": "ca",
    "Schottland": "gb-sct", "Paraguay": "py", "Elfenbeinküste": "ci", "Tschechien": "cz",
    "Ägypten": "eg", "Bosnien Herzegowina": "ba", "Algerien": "dz", "Südkorea": "kr",
    "Australien": "au", "Ghana": "gh", "Iran": "ir", "Tunesien": "tn",
    "DR Kongo": "cd", "Südafrika": "za", "Saudi Arabien": "sa", "Katar": "qa",
    "Irak": "iq", "Neuseeland": "nz", "Panama": "pa", "Usbekistan": "uz",
    "Kap Verde": "cv", "Jordanien": "jo", "Curacao": "cw", "Haiti": "ht",
}

# Kürzere Anzeigenamen für mehr Konsistenz in der Länge
DISPLAY_NAMES = {
    "Bosnien Herzegowina": "Bosnien",
}

# ---------------------------------------------------------------------------
# Ausgeschiedene Teams
# ---------------------------------------------------------------------------
# Teams, die das Turnier verlassen haben, hier mit Austrittsphase eintragen.
# Teamname: exakt wie in VALID_TEAMS (update_processed_data.py), also auf Deutsch.
# Mögliche Werte: "Gruppenphase", "Achtelfinale", "Viertelfinale", "Halbfinale", "Finale"
#
# Nicht eingetragene Teams, die im neuesten Snapshot fehlen, werden automatisch
# erkannt und als "Gruppenphase" beschriftet.
ELIMINATED = {
    "Haiti":    "Gruppenphase",
    "Tunesien": "Gruppenphase",
    "Türkei":   "Gruppenphase",
    "Jordanien":  "Gruppenphase",
    "Panama":    "Gruppenphase",
    "Katar":     "Gruppenphase",
    "Tschechien": "Gruppenphase",
    "Curacao":   "Gruppenphase",
}

STAGE_LABEL = {
    "Gruppenphase":  "Ausgeschieden · Gruppenphase",
    "Achtelfinale":  "Ausgeschieden · Achtelfinale",
    "Viertelfinale": "Ausgeschieden · Viertelfinale",
    "Halbfinale":    "Ausgeschieden · Halbfinale",
    "Finale":        "Ausgeschieden · Finale",
}


# ---------------------------------------------------------------------------
# Flaggen laden (mit lokalem Cache)
# ---------------------------------------------------------------------------

def get_flag(team):
    code = FLAG_CODES[team]
    path = os.path.join(FLAG_DIR, f"{code}_w160.png")
    if not os.path.exists(path):
        os.makedirs(FLAG_DIR, exist_ok=True)
        urllib.request.urlretrieve(f"https://flagcdn.com/w160/{code}.png", path)
    return plt.imread(path)


def _fade_img(img: np.ndarray, alpha: float = 0.32) -> np.ndarray:
    """Blendet das Bild mit Weiß, um ausgeschiedene Teams gedimmt darzustellen."""
    if img.ndim == 3 and img.shape[2] == 4:   # RGBA: nur RGB-Kanäle dimmen
        rgb   = img[:, :, :3] * alpha + (1.0 - alpha)
        return np.concatenate([rgb, img[:, :, 3:4]], axis=2)
    return img * alpha + (1.0 - alpha)         # RGB


def _draw_cross(fig, cx: float, cy: float, fig_w_in: float, fig_h_in: float) -> None:
    """Zeichnet ein rotes × in Figurkoordinaten bei (cx, cy)."""
    # Physisch gleich lange Kreuzarme: 14 px bei 200 dpi
    px    = 14 / 200
    sx    = px / fig_w_in
    sy    = px / fig_h_in
    for x0, y0, x1, y1 in [
        (cx - sx, cy - sy, cx + sx, cy + sy),
        (cx - sx, cy + sy, cx + sx, cy - sy),
    ]:
        fig.add_artist(Line2D([x0, x1], [y0, y1], transform=fig.transFigure,
                               color="#CC0000", linewidth=2.5, clip_on=False, zorder=10))


# ---------------------------------------------------------------------------
# Daten laden
# ---------------------------------------------------------------------------

def _load_long(filepath):
    """Lädt eine processed_data_long.xlsx. None falls (noch) keine Daten vorhanden."""
    if not os.path.exists(filepath):
        return None
    df = pd.read_excel(filepath)
    if df.empty or df.columns.empty:
        return None
    df.columns = df.columns.astype(str).str.strip()
    df["Datum"] = pd.to_datetime(df["Datum"])
    df["Team"]  = df["Team"].astype(str).str.strip()
    return df


def load_data():
    """
    Lädt die durchgehende Zeitreihe der Shin-Wahrscheinlichkeiten:
    pre_wm-Snapshots + during_wm-Snapshots (ab WM-Start, sobald vorhanden),
    nach Datum sortiert. Wächst automatisch mit jedem neuen Snapshot.
    """
    df        = _load_long(PRE_WM_LONG_FILE)
    df_during = _load_long(DURING_WM_LONG_FILE)
    if df_during is not None and not df_during.empty:
        df = pd.concat([df, df_during], ignore_index=True)
    return df.sort_values("Datum").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 1) Balkendiagramm: alle 48 Teams
# ---------------------------------------------------------------------------

def _get_eliminated_df(df: pd.DataFrame, latest_teams: set) -> pd.DataFrame:
    """
    Ermittelt ausgeschiedene Teams:
    1. Explizit in ELIMINATED eingetragen.
    2. Automatisch: waren in during_wm-Daten, fehlen aber im neuesten Snapshot.
    Gibt DataFrame mit Spalten [Team, Prob, Stage] zurück.
    """
    during_wm_teams: set = set()
    if os.path.exists(DURING_WM_LONG_FILE):
        df_d = _load_long(DURING_WM_LONG_FILE)
        if df_d is not None:
            during_wm_teams = set(df_d["Team"].unique())

    auto_detected = during_wm_teams - latest_teams

    # Teams im neuesten Snapshot mit NaN-Wahrscheinlichkeit: Buchmacher zeigen
    # keine Quoten mehr → ebenfalls als ausgeschieden behandeln.
    latest_date = df["Datum"].max()
    nan_teams = set(
        df[(df["Datum"] == latest_date) & df["Wahrscheinlichkeit_Shin_in_Prozent"].isna()]["Team"]
    )

    # Manuell eingetragene Teams immer als ausgeschieden behandeln –
    # auch wenn Buchmacher noch Quoten zeigen (und sie im latest-Snapshot stehen).
    all_eliminated = set(ELIMINATED.keys()) | auto_detected | nan_teams

    records = []
    for team in sorted(all_eliminated):
        team_df = df[df["Team"] == team]
        if team_df.empty:
            continue
        probs      = team_df.sort_values("Datum")["Wahrscheinlichkeit_Shin_in_Prozent"].dropna()
        last_prob  = probs.iloc[-1] if not probs.empty else 0.0
        stage_key  = ELIMINATED.get(team, "Gruppenphase")
        stage_text = STAGE_LABEL.get(stage_key, f"Ausgeschieden · {stage_key}")
        records.append({"Team": team, "Prob": last_prob, "Stage": stage_text})

    if not records:
        return pd.DataFrame(columns=["Team", "Prob", "Stage"])
    return (pd.DataFrame(records)
              .sort_values("Prob", ascending=False)
              .reset_index(drop=True))


def build_bar_chart(df):
    latest       = df["Datum"].max()
    latest_teams = set(df[df["Datum"] == latest]["Team"].unique())

    elim_df = _get_eliminated_df(df, latest_teams)
    all_eliminated_teams = set(elim_df["Team"])

    # Aktive Teams: im neuesten Snapshot vorhanden, nicht ausgeschieden, Wert nicht NaN
    sub_active = (
        df[(df["Datum"] == latest) & (~df["Team"].isin(all_eliminated_teams))
           & df["Wahrscheinlichkeit_Shin_in_Prozent"].notna()]
        .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
        .reset_index(drop=True)
    )

    n_active = len(sub_active)
    n_elim   = len(elim_df)
    n        = n_active + n_elim

    teams_active  = sub_active["Team"].tolist()
    values_active = sub_active["Wahrscheinlichkeit_Shin_in_Prozent"].to_numpy()
    teams_elim    = elim_df["Team"].tolist()
    values_elim   = elim_df["Prob"].to_numpy() if n_elim else np.array([])
    stages_elim   = elim_df["Stage"].tolist()

    all_values = np.concatenate([values_active, values_elim]) if n_elim else values_active
    x_max      = all_values.max() * 1.10

    y      = np.arange(n)
    fig_w  = 10.0
    fig_h  = 0.335 * n + 1.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    plt.subplots_adjust(left=0.26, right=0.965,
                        top=1 - 0.85 / fig_h, bottom=0.2 / fig_h)

    # Aktive Teams – farbige Balken
    colors_active = ["#E63946" if t == "Deutschland" else "#457B9D" for t in teams_active]
    ax.barh(y[:n_active], values_active, color=colors_active, height=0.62, zorder=3)

    # Ausgeschiedene Teams – graue Balken
    if n_elim:
        ax.barh(y[n_active:], values_elim, color="#CCCCCC", height=0.62, zorder=3)

    ax.invert_yaxis()
    ax.set_yticks([])
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xlim(0, x_max)
    ax.set_xticks([])

    # ---- Aktive Teams: Flagge + Name + Prozentzahl ----
    for i, (team, val) in enumerate(zip(teams_active, values_active)):
        y_fig = fig.transFigure.inverted().transform(ax.transData.transform((0, i)))[1]

        ab = AnnotationBbox(OffsetImage(get_flag(team), zoom=0.155),
                            (0.018, y_fig), xycoords="figure fraction",
                            frameon=False, box_alignment=(0, 0.5), annotation_clip=False)
        ax.add_artist(ab)

        weight = "bold" if team == "Deutschland" else "medium"
        ax.text(0.078, y_fig, DISPLAY_NAMES.get(team, team),
                transform=fig.transFigure, ha="left", va="center",
                fontsize=10, fontweight=weight, color="#2C3E50")
        ax.text(val + all_values.max() * 0.012, i,
                f"{val:.2f}%".replace(".", ","),
                va="center", ha="left", fontsize=9, fontweight="medium", color="#333")

    # ---- Trennlinie zwischen aktiven und ausgeschiedenen Teams ----
    if n_elim:
        ax.axhline(y=n_active - 0.5, color="#BBBBBB", linewidth=1.0, linestyle="--", zorder=2)

    # ---- Ausgeschiedene Teams: gedimmte Flagge + rotes × + grauer Name + Stage-Text ----
    for j, (team, val, stage) in enumerate(zip(teams_elim, values_elim, stages_elim)):
        i     = n_active + j
        y_fig = fig.transFigure.inverted().transform(ax.transData.transform((0, i)))[1]

        # Gedimmte Flagge
        ab = AnnotationBbox(OffsetImage(_fade_img(get_flag(team)), zoom=0.155),
                            (0.018, y_fig), xycoords="figure fraction",
                            frameon=False, box_alignment=(0, 0.5), annotation_clip=False)
        ax.add_artist(ab)

        # Rotes × über der Flagge
        _draw_cross(fig, cx=0.018, cy=y_fig, fig_w_in=fig_w, fig_h_in=fig_h)

        # Grauer Teamname
        ax.text(0.078, y_fig, DISPLAY_NAMES.get(team, team),
                transform=fig.transFigure, ha="left", va="center",
                fontsize=10, fontweight="medium", color="#999999")

        # Stage-Text statt Prozentzahl
        ax.text(val + all_values.max() * 0.012, i, stage,
                va="center", ha="left", fontsize=8.5, style="italic", color="#AAAAAA")

    ax.set_title(
        f"Siegwahrscheinlichkeiten aller 48 Teams\n"
        f"Stand: {latest.strftime('%d.%m.%Y')}",
        fontsize=14, fontweight="bold", color="#2C3E50", pad=14,
    )
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)

    fig.text(0.005, 0.005,
             "Institut für Trainingswissenschaft und Sportinformatik  ·  Lukas Gardeweg, Fabian Wunderlich und Daniel Memmert",
             fontsize=8, color="#AAAAAA")

    fig.savefig(BAR_OUTPUT, dpi=200)
    plt.close(fig)
    print(f"Gespeichert: {BAR_OUTPUT}")


# ---------------------------------------------------------------------------
# 2) Zeitverlauf: Top 15 Teams vor der WM
# ---------------------------------------------------------------------------

def spread_label_positions(values, min_gap, n_iter=2000):
    """Verteilt Label-Positionen iterativ, sodass sie sich nicht überlappen."""
    pos   = np.array(values, dtype=float)
    order = np.argsort(pos)
    for _ in range(n_iter):
        moved = False
        for a, b in zip(order[:-1], order[1:]):
            gap = pos[b] - pos[a]
            if gap < min_gap:
                shift = (min_gap - gap) / 2
                pos[a] -= shift
                pos[b] += shift
                moved = True
        if not moved:
            break
    return pos


def build_line_chart(df):
    latest  = df["Datum"].max()

    # Ranking nach letztem verfügbaren Wert pro Team – so bleiben ausgeschiedene
    # Teams in der Top-15 sichtbar, auch wenn sie im neuesten Snapshot fehlen.
    top15 = (
        df.sort_values("Datum")
          .groupby("Team", as_index=False)
          .last()
          .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
          ["Team"].tolist()
    )[:15]

    fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
    plt.subplots_adjust(left=0.065, right=0.95, top=0.88, bottom=0.13)

    dates      = sorted(df["Datum"].unique())
    first_date = dates[0]
    last_date  = dates[-1]
    span_days  = (last_date - first_date).days

    final_values     = []
    last_team_dates  = []
    for i, team in enumerate(top15):
        tdf = df[df["Team"] == team].sort_values("Datum")
        ax.plot(tdf["Datum"], tdf["Wahrscheinlichkeit_Shin_in_Prozent"],
                marker="o", markersize=4.5, linewidth=2.2,
                color=COLORS[i % len(COLORS)], zorder=3)
        final_values.append(tdf["Wahrscheinlichkeit_Shin_in_Prozent"].iloc[-1])
        last_team_dates.append(tdf["Datum"].iloc[-1])

    final_values = np.array(final_values)
    y_max = final_values.max()

    ax.set_xlim(first_date - pd.Timedelta(days=span_days * 0.02),
                last_date + pd.Timedelta(days=span_days * 0.06))

    ylim_top_provisional = y_max * 1.18
    ax.set_ylim(min(0, final_values.min() - y_max * 0.03), ylim_top_provisional)
    axes_height_pt = fig.get_size_inches()[1] * 72 * (0.88 - 0.10)
    pts_per_unit   = axes_height_pt / (ylim_top_provisional - ax.get_ylim()[0])
    min_gap        = 22 / pts_per_unit

    label_y = spread_label_positions(final_values, min_gap=min_gap)
    ax.set_ylim(min(0, final_values.min() - y_max * 0.03, label_y.min() - min_gap * 0.6),
                max(ylim_top_provisional, label_y.max() + min_gap * 0.8))

    label_x = last_date + pd.Timedelta(days=span_days * 0.085)
    flag_x  = last_date + pd.Timedelta(days=span_days * 0.035)

    for i, (team, val, ly, team_last_date) in enumerate(zip(top15, final_values, label_y, last_team_dates)):
        color = COLORS[i % len(COLORS)]
        if abs(ly - val) > min_gap * 0.15:
            ax.plot([team_last_date, flag_x], [val, ly], color=color,
                    linewidth=0.8, alpha=0.5, zorder=2)

        img = get_flag(team)
        ab = AnnotationBbox(
            OffsetImage(img, zoom=0.135), (flag_x, ly),
            frameon=False, box_alignment=(0, 0.5), annotation_clip=False,
        )
        ax.add_artist(ab)

    # Vertikale Linie: WM-Start
    wm_start = pd.Timestamp(wm_paths.WM_START_DATE)
    if first_date < wm_start < last_date + pd.Timedelta(days=1):
        ax.axvline(wm_start, color="#888888", linewidth=1.2, linestyle="--", zorder=2)
        ax.text(wm_start + pd.Timedelta(days=span_days * 0.008),
                ax.get_ylim()[1] * 0.985,
                "WM-Start", fontsize=8.5, color="#666666", va="top")

    ax.set_ylabel("Siegwahrscheinlichkeit (%)", fontsize=11)
    ax.set_xlabel("Datum", fontsize=11)
    ax.set_title(
        f"Zeitverlauf der Top 15 Siegwahrscheinlichkeiten\n"
        f"Stand: {last_date.strftime('%d.%m.%Y')}",
        fontsize=14, fontweight="bold", color="#2C3E50", pad=14,
    )

    max_ticks = 20
    if len(dates) <= max_ticks:
        tick_dates = dates
    else:
        step = -(-len(dates) // max_ticks)
        tick_dates = dates[::step]
        if tick_dates[-1] != dates[-1]:
            tick_dates = tick_dates + [dates[-1]]
    ax.set_xticks(tick_dates)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d.%m."))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9.5)
    ax.tick_params(axis="y", labelsize=9.5)
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    ax.grid(color="#E8E8E8", zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.text(0.005, 0.005,
             "Institut für Trainingswissenschaft und Sportinformatik  ·  Lukas Gardeweg, Fabian Wunderlich und Daniel Memmert",
             fontsize=8, color="#AAAAAA")

    fig.savefig(LINE_OUTPUT, dpi=200)
    plt.close(fig)
    print(f"Gespeichert: {LINE_OUTPUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    df = load_data()
    missing = set(df["Team"].unique()) - set(FLAG_CODES)
    if missing:
        raise ValueError(f"Keine Flaggen-Zuordnung für: {missing}")

    print("Erzeuge Balkendiagramm (alle 48 Teams)...")
    build_bar_chart(df)

    print("Erzeuge Zeitverlauf (Top 15)...")
    build_line_chart(df)


if __name__ == "__main__":
    main()