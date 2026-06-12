# -*- coding: utf-8 -*-
"""
create_png_charts.py
Erzeugt zwei publikationsreife PNG-Grafiken aus den aktuellen
Shin-Wahrscheinlichkeiten (vor der WM):

  1. Balkendiagramm: aktuelle Shin-Wahrscheinlichkeiten aller 48 Teams
  2. Zeitverlauf: Top 15 Teams (Shin-Wahrscheinlichkeit) vor der WM

Beide Grafiken sind mit den jeweiligen Landesflaggen beschriftet.

Verwendung: python create_png_charts.py
"""

import os
import urllib.request

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

BASE             = os.path.dirname(os.path.abspath(__file__))
PRE_WM_LONG_FILE = os.path.join(BASE, "processed_data_pre_wm", "processed_data_long.xlsx")
FLAG_DIR         = os.path.join(BASE, "flags")
BAR_OUTPUT       = os.path.join(BASE, "wm2026_balkendiagramm_alle_teams.png")
LINE_OUTPUT      = os.path.join(BASE, "wm2026_zeitverlauf_top15_vor_wm.png")

# Enddatum für die Auswertung (None = neuestes verfügbares Datum verwenden)
# für beliebiges Datum 
#CUTOFF_DATE = None
CUTOFF_DATE = "2026-06-05"

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
# Flaggen laden (mit lokalem Cache)
# ---------------------------------------------------------------------------

def get_flag(team):
    code = FLAG_CODES[team]
    path = os.path.join(FLAG_DIR, f"{code}_w160.png")
    if not os.path.exists(path):
        os.makedirs(FLAG_DIR, exist_ok=True)
        urllib.request.urlretrieve(f"https://flagcdn.com/w160/{code}.png", path)
    return plt.imread(path)


# ---------------------------------------------------------------------------
# Daten laden
# ---------------------------------------------------------------------------

def load_data():
    df = pd.read_excel(PRE_WM_LONG_FILE)
    df.columns = df.columns.astype(str).str.strip()
    df["Datum"] = pd.to_datetime(df["Datum"])
    df["Team"]  = df["Team"].astype(str).str.strip()
    if CUTOFF_DATE is not None:
        df = df[df["Datum"] <= pd.Timestamp(CUTOFF_DATE)]
    return df


# ---------------------------------------------------------------------------
# 1) Balkendiagramm: alle 48 Teams
# ---------------------------------------------------------------------------

def build_bar_chart(df):
    latest = df["Datum"].max()
    sub = (df[df["Datum"] == latest]
           .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
           .reset_index(drop=True))

    n      = len(sub)
    teams  = sub["Team"].tolist()
    values = sub["Wahrscheinlichkeit_Shin_in_Prozent"].to_numpy()
    y      = np.arange(n)

    fig_h = 0.335 * n + 1.0
    fig, ax = plt.subplots(figsize=(10, fig_h), dpi=200)

    #plt.subplots_adjust(left=0.305, right=0.965,
                         #top=1 - 1.05 / fig_h, bottom=0.55 / fig_h)
    #plt.subplots_adjust(left=0.26, right=0.965,
                         #top=1 - 1.05 / fig_h, bottom=0.15 / fig_h)
    plt.subplots_adjust(left=0.26, right=0.965,
                         top=1 - 0.85 / fig_h, bottom=0.2 / fig_h)

    colors = ["#E63946" if t == "Deutschland" else "#457B9D" for t in teams]
    ax.barh(y, values, color=colors, height=0.62, zorder=3)
    ax.invert_yaxis()
    ax.set_yticks([])
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xlim(0, values.max() * 1.10)
    ax.set_xticks([])

    for i, (team, val) in enumerate(zip(teams, values)):
        y_fig = fig.transFigure.inverted().transform(ax.transData.transform((0, i)))[1]

        img = get_flag(team)
        ab = AnnotationBbox(
            OffsetImage(img, zoom=0.155), (0.018, y_fig),
            xycoords="figure fraction", frameon=False,
            box_alignment=(0, 0.5), annotation_clip=False,
        )
        ax.add_artist(ab)

        #weight = "bold" if team == "Deutschland" else "normal"
        weight = "bold" if team == "Deutschland" else "medium"
        #ax.text(0.078, y_fig, team, transform=fig.transFigure, ha="left", va="center",
                #fontsize=9.5, fontweight=weight, color="#2C3E50")
        #ax.text(0.078, y_fig, DISPLAY_NAMES.get(team, team), transform=fig.transFigure, ha="left", va="center",
                #fontsize=9.5, fontweight=weight, color="#2C3E50")
        ax.text(0.078, y_fig, DISPLAY_NAMES.get(team, team), transform=fig.transFigure, ha="left", va="center",
                fontsize=10, fontweight=weight, color="#2C3E50")

        #ax.text(val + values.max() * 0.012, i, f"{val:.2f}%".replace(".", ","),
                #va="center", ha="left", fontsize=8.5, color="#444")
        ax.text(val + values.max() * 0.012, i, f"{val:.2f}%".replace(".", ","),
                va="center", ha="left", fontsize=9, fontweight="medium", color="#333")

    #ax.set_xlabel("Siegwahrscheinlichkeit (%)", fontsize=11)
    ax.set_title(
        f"Siegwahrscheinlichkeiten aller 48 Teams\n"
        f"Stand: {latest.strftime('%d.%m.%Y')}",
        fontsize=14, fontweight="bold", color="#2C3E50", pad=14,
    )
    #ax.grid(axis="x", color="#E8E8E8", zorder=0)
    ax.set_axisbelow(True)
    #for spine in ("top", "right", "left"):
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
    ranking = (df[df["Datum"] == latest]
               .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
               ["Team"].tolist())
    top15 = ranking[:15]

    fig, ax = plt.subplots(figsize=(12, 8), dpi=200)
    #plt.subplots_adjust(left=0.065, right=0.78, top=0.88, bottom=0.10)
    #plt.subplots_adjust(left=0.065, right=0.95, top=0.88, bottom=0.10)
    plt.subplots_adjust(left=0.065, right=0.95, top=0.88, bottom=0.13)

    dates      = sorted(df["Datum"].unique())
    first_date = dates[0]
    last_date  = dates[-1]
    span_days  = (last_date - first_date).days

    final_values = []
    for i, team in enumerate(top15):
        tdf = df[df["Team"] == team].sort_values("Datum")
        ax.plot(tdf["Datum"], tdf["Wahrscheinlichkeit_Shin_in_Prozent"],
                marker="o", markersize=4.5, linewidth=2.2,
                color=COLORS[i % len(COLORS)], zorder=3)
        final_values.append(tdf["Wahrscheinlichkeit_Shin_in_Prozent"].iloc[-1])

    final_values = np.array(final_values)
    y_max = final_values.max()

    ax.set_xlim(first_date - pd.Timedelta(days=span_days * 0.02),
                last_date + pd.Timedelta(days=span_days * 0.06))

    # Mindestabstand zwischen Labels in Datenkoordinaten, abgeleitet aus der
    # Achsenhöhe in Punkten (~22pt pro Label inkl. Flagge).
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

    for i, (team, val, ly) in enumerate(zip(top15, final_values, label_y)):
        color = COLORS[i % len(COLORS)]
        if abs(ly - val) > min_gap * 0.15:
            ax.plot([last_date, flag_x], [val, ly], color=color,
                    linewidth=0.8, alpha=0.5, zorder=2)

        img = get_flag(team)
        ab = AnnotationBbox(
            OffsetImage(img, zoom=0.135), (flag_x, ly),
            frameon=False, box_alignment=(0, 0.5), annotation_clip=False,
        )
        ax.add_artist(ab)

        #rank    = i + 1
        #val_str = f"{val:.1f}%".replace(".", ",")
        #ax.text(label_x, ly, f"{rank}. {team}   {val_str}",
                #va="center", ha="left", fontsize=10,
                #fontweight="bold" if team == "Deutschland" else "normal",
                #color=color)

    ax.set_ylabel("Siegwahrscheinlichkeit (%)", fontsize=11)
    ax.set_xlabel("Datum", fontsize=11)
    ax.set_title(
        f"Zeitverlauf der Top 15 Siegwahrscheinlichkeiten vor der WM\n",
        #f"Stand: · {first_date.strftime('%d.%m.%Y')} – {last_date.strftime('%d.%m.%Y')}",
        fontsize=14, fontweight="bold", color="#2C3E50", pad=14,
    )

    ax.set_xticks(dates)
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

    print("Erzeuge Zeitverlauf (Top 15, vor der WM)...")
    build_line_chart(df)


if __name__ == "__main__":
    main()
