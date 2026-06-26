# -*- coding: utf-8 -*-
"""
create_control_charts.py

Führt die Zeitreihen aus processed_data_pre_wm und processed_data_during_wm
zusammen und erstellt eine Kontroll-Visualisierung mit allen Teams.

Ausgabe in control/:
  merged_long.xlsx            – vollständige Long-Format-Zeitreihe (pre + during)
  merged_wide.xlsx            – entsprechendes Wide-Format
  zeitverlauf_alle_teams.png  – Zeitverlauf aller Teams als Kontrollgrafik

Verwendung: python control/create_control_charts.py
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE         = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.dirname(BASE)
PRE_WM_FILE  = os.path.join(ROOT, "processed_data_pre_wm",    "processed_data_long.xlsx")
DURING_FILE  = os.path.join(ROOT, "processed_data_during_wm", "processed_data_long.xlsx")
MERGED_LONG  = os.path.join(BASE, "merged_long.xlsx")
MERGED_WIDE  = os.path.join(BASE, "merged_wide.xlsx")
CHART_OUT    = os.path.join(BASE, "zeitverlauf_alle_teams.png")

WM_START = pd.Timestamp("2026-06-11")

sys.path.insert(0, os.path.join(ROOT, "visualization_png"))
try:
    from create_png_charts import ELIMINATED
except ImportError:
    ELIMINATED = {}


# ---------------------------------------------------------------------------
# Daten laden & zusammenführen
# ---------------------------------------------------------------------------

def load_long(filepath: str) -> pd.DataFrame:
    if not os.path.exists(filepath):
        return pd.DataFrame()
    df = pd.read_excel(filepath)
    if df.empty or df.columns.empty:
        return pd.DataFrame()
    df.columns = df.columns.astype(str).str.strip()
    df["Datum"] = pd.to_datetime(df["Datum"])
    df["Team"]  = df["Team"].astype(str).str.strip()
    return df


def merge_data() -> pd.DataFrame:
    df_pre    = load_long(PRE_WM_FILE)
    df_during = load_long(DURING_FILE)

    parts = [df for df in [df_pre, df_during] if not df.empty]
    if not parts:
        raise ValueError("Keine Daten in pre_wm oder during_wm vorhanden.")

    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values(
        ["Datum", "Wahrscheinlichkeit_Shin_in_Prozent"],
        ascending=[True, False],
        na_position="last",
    ).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Wide-Format
# ---------------------------------------------------------------------------

def build_wide(df_long: pd.DataFrame) -> pd.DataFrame:
    df        = df_long.copy()
    snapshots = sorted(df["Datum"].unique())
    if not snapshots:
        return pd.DataFrame({"Team": []})

    # Teams nach letztem gültigem Shin-Wert sortieren; Teams ohne Werte ans Ende
    last_valid = (
        df.dropna(subset=["Wahrscheinlichkeit_Shin_in_Prozent"])
        .sort_values("Datum")
        .groupby("Team", as_index=False)
        .last()
        .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
    )
    teams  = last_valid["Team"].tolist()
    extras = [t for t in sorted(df["Team"].unique()) if t not in teams]
    teams += extras

    result = pd.DataFrame({"Team": teams})
    for i, datum in enumerate(snapshots, start=1):
        snap = df[df["Datum"] == datum].set_index("Team")
        result[f"Datum_{i}"]                              = datum.strftime("%d.%m.%Y")
        result[f"Durchsch_Quote_{i}"]                     = result["Team"].map(snap["Durchsch_Quote"]).round(2)
        result[f"Norm_Wahrscheinlichkeit_in_Prozent_{i}"] = result["Team"].map(snap["Wahrscheinlichkeit_in_Prozent"]).round(2)
        result[f"Shin_Wahrscheinlichkeit_in_Prozent_{i}"] = result["Team"].map(snap["Wahrscheinlichkeit_Shin_in_Prozent"]).round(2)
    return result


# ---------------------------------------------------------------------------
# Kontroll-Zeitverlauf
# ---------------------------------------------------------------------------

def spread_labels(values: list[float], min_gap: float, n_iter: int = 3000) -> np.ndarray:
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


def create_chart(df: pd.DataFrame) -> None:
    dates      = sorted(df["Datum"].unique())
    first_date = dates[0]
    last_date  = dates[-1]
    span_days  = max((last_date - first_date).days, 1)

    # Teams nach letztem gültigem Shin-Wert sortieren
    last_valid_df = (
        df.dropna(subset=["Wahrscheinlichkeit_Shin_in_Prozent"])
        .sort_values("Datum")
        .groupby("Team", as_index=False)
        .last()
        .sort_values("Wahrscheinlichkeit_Shin_in_Prozent", ascending=False)
    )
    teams_ranked = last_valid_df["Team"].tolist()
    active_teams = [t for t in teams_ranked if t not in ELIMINATED]
    elim_teams   = [t for t in teams_ranked if t in ELIMINATED]

    # Farben: Tab20 + Tab20b = 40 Farben
    color_pool = list(plt.cm.tab20.colors) + list(plt.cm.tab20b.colors)

    fig, ax = plt.subplots(figsize=(17, 11), dpi=150)
    plt.subplots_adjust(left=0.05, right=0.75, top=0.90, bottom=0.09)

    label_infos = []

    # Aktive Teams – solide Linien
    for i, team in enumerate(active_teams):
        tdf = (
            df[df["Team"] == team]
            .sort_values("Datum")
            .dropna(subset=["Wahrscheinlichkeit_Shin_in_Prozent"])
        )
        if tdf.empty:
            continue
        color = color_pool[i % len(color_pool)]
        ax.plot(
            tdf["Datum"], tdf["Wahrscheinlichkeit_Shin_in_Prozent"],
            marker="o", markersize=3.5, linewidth=1.8, color=color, zorder=3,
        )
        label_infos.append({
            "team":      team,
            "raw_y":     float(tdf["Wahrscheinlichkeit_Shin_in_Prozent"].iloc[-1]),
            "last_date": tdf["Datum"].iloc[-1],
            "color":     color,
            "eliminated": False,
        })

    # Ausgeschiedene Teams – gestrichelte graue Linien
    for team in elim_teams:
        tdf = (
            df[df["Team"] == team]
            .sort_values("Datum")
            .dropna(subset=["Wahrscheinlichkeit_Shin_in_Prozent"])
        )
        if tdf.empty:
            continue
        ax.plot(
            tdf["Datum"], tdf["Wahrscheinlichkeit_Shin_in_Prozent"],
            marker="o", markersize=2, linewidth=1.0, color="#CCCCCC",
            linestyle="--", zorder=2,
        )
        label_infos.append({
            "team":      team,
            "raw_y":     float(tdf["Wahrscheinlichkeit_Shin_in_Prozent"].iloc[-1]),
            "last_date": tdf["Datum"].iloc[-1],
            "color":     "#AAAAAA",
            "eliminated": True,
        })

    # Achsenbereiche setzen
    ax.set_xlim(
        first_date - pd.Timedelta(days=max(int(span_days * 0.02), 2)),
        last_date  + pd.Timedelta(days=max(int(span_days * 0.30), 10)),
    )
    all_vals = [info["raw_y"] for info in label_infos]
    y_max    = max(all_vals) if all_vals else 30
    ax.set_ylim(-0.3, y_max * 1.18)

    # WM-Start-Linie
    if first_date <= WM_START <= last_date:
        ax.axvline(WM_START, color="#888888", linewidth=1.0, linestyle=":", zorder=1)
        ax.text(
            WM_START + pd.Timedelta(days=max(int(span_days * 0.004), 1)),
            y_max * 1.13,
            "WM-Start",
            fontsize=8, color="#888888", va="top", ha="left",
        )

    # Label-Positionen berechnen (spread um Überlappung zu vermeiden)
    axes_h_pt    = fig.get_size_inches()[1] * 72 * (0.90 - 0.09)
    ylim_range   = ax.get_ylim()[1] - ax.get_ylim()[0]
    pts_per_unit = axes_h_pt / ylim_range if ylim_range else 1
    min_gap      = 8.5 / pts_per_unit      # ~8.5 pt Schriftgröße

    raw_ys    = [info["raw_y"] for info in label_infos]
    spread_ys = spread_labels(raw_ys, min_gap)

    label_x_offset = pd.Timedelta(days=max(int(span_days * 0.060), 4))
    label_x        = last_date + label_x_offset
    text_x          = last_date + label_x_offset + pd.Timedelta(days=max(int(span_days * 0.003), 1))

    for info, ly in zip(label_infos, spread_ys):
        raw   = info["raw_y"]
        color = info["color"]
        ldate = info["last_date"]
        if abs(ly - raw) > min_gap * 0.15:
            ax.plot(
                [ldate, label_x], [raw, ly],
                color=color, linewidth=0.5, alpha=0.35, zorder=1,
            )
        label_txt = f"{info['team']} ✗" if info["eliminated"] else info["team"]
        ax.text(
            text_x, ly, label_txt,
            fontsize=6.5, color=color, va="center",
            fontweight="medium" if not info["eliminated"] else "normal",
        )

    # Formatierung
    n_snapshots = len(dates)
    max_ticks   = 20
    if n_snapshots <= max_ticks:
        tick_dates = list(dates)
    else:
        step       = -(-n_snapshots // max_ticks)
        tick_dates = list(dates[::step])
        if tick_dates[-1] != dates[-1]:
            tick_dates.append(dates[-1])

    ax.set_xticks(tick_dates)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d.%m."))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)
    ax.tick_params(axis="y", labelsize=9)
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    ax.set_xlabel("Datum", fontsize=10)
    ax.set_ylabel("Siegwahrscheinlichkeit Shin (%)", fontsize=10)
    ax.set_title(
        f"Kontroll-Zeitverlauf: Siegwahrscheinlichkeiten aller Teams "
        f"(pre_wm + during_wm)\n"
        f"Stand: {last_date.strftime('%d.%m.%Y')}  |  "
        f"{n_snapshots} Schnappschüsse  |  {len(label_infos)} Teams",
        fontsize=12, fontweight="bold", color="#2C3E50", pad=10,
    )
    ax.grid(color="#EBEBEB", zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.text(
        0.005, 0.005,
        "Institut für Trainingswissenschaft und Sportinformatik  ·  "
        "Lukas Gardeweg, Fabian Wunderlich und Daniel Memmert",
        fontsize=7.5, color="#BBBBBB",
    )

    fig.savefig(CHART_OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Gespeichert: {CHART_OUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  create_control_charts.py")
    print("=" * 55)

    df = merge_data()

    n_snap  = df["Datum"].nunique()
    n_teams = df["Team"].nunique()
    print(f"\nMerge: {n_snap} Snapshots, {n_teams} Teams")

    df.to_excel(MERGED_LONG, index=False)
    print(f"Long:  {MERGED_LONG}")

    df_wide = build_wide(df)
    df_wide.to_excel(MERGED_WIDE, index=False)
    n_wide_snap = (len(df_wide.columns) - 1) // 4
    print(f"Wide:  {MERGED_WIDE}  ({len(df_wide)} Teams × {n_wide_snap} Zeitpunkte)")

    print("\nErzeuge Zeitverlauf-Grafik (alle Teams)...")
    create_chart(df)

    print("\nFertig.")


if __name__ == "__main__":
    main()
