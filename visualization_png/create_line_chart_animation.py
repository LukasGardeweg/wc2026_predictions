# -*- coding: utf-8 -*-
"""
create_line_chart_animation.py
Erzeugt eine animierte MP4-Version des Zeitverlaufs der Top-15
Siegwahrscheinlichkeiten (wm2026_zeitverlauf_top15.png): Die Kurven wachsen
flüssig (interpoliert zwischen den echten Erhebungsterminen) über den
gesamten Turnierverlauf, statt von Termin zu Termin zu springen. Die
Animation endet optisch identisch zum statischen PNG.

Läuft nicht automatisch bei jedem run_all.py-Durchlauf mit, sondern wird bei
Bedarf manuell erzeugt (finale Zusammenfassung).

Benötigt ffmpeg im PATH (für MP4-Export über matplotlib).

Verwendung: python create_line_chart_animation.py
"""

import os
import sys

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, writers
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import create_png_charts as cpc

ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import wm_paths

OUTPUT = os.path.join(BASE, "wm2026_zeitverlauf_top15_animation.mp4")

# ---------------------------------------------------------------------------
# Timing – ruhiges, flüssiges Tempo statt harter Datum-zu-Datum-Sprünge
# ---------------------------------------------------------------------------
FPS                  = 30
HOLD_START_SECONDS   = 1.5     # Pause auf dem Startzustand, bevor es losgeht
GROWTH_SECONDS        = 26.0    # Dauer des eigentlichen "Anwachsens" der Kurven
HOLD_END_SECONDS     = 5.0     # Pause auf dem finalen Zustand (= statisches PNG)
BLEND_START_FRACTION = 0.85     # ab welchem Fortschrittsanteil die Flaggen sanft
                                # in ihre finale (überlappungsfreie) Position gleiten
REFLINE_FADE_DAYS    = 2.5      # Einblenddauer der gestrichelten Ereignislinien


def _check_ffmpeg() -> None:
    if writers.is_available("ffmpeg"):
        return
    raise RuntimeError(
        "ffmpeg wurde nicht gefunden (benötigt für den MP4-Export). "
        "Bitte installieren, z. B. mit 'winget install ffmpeg' oder "
        "'choco install ffmpeg', und danach das Terminal neu starten."
    )


def _ease_in_out_cubic(p: np.ndarray) -> np.ndarray:
    """Sanfter Start, zügige Mitte, sanftes Ausklingen – wirkt ruhiger als lineares Tempo."""
    return np.where(p < 0.5, 4 * p ** 3, 1 - (-2 * p + 2) ** 3 / 2)


def _smoothstep(x: float, edge0: float, edge1: float) -> float:
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _prepare_team_series(df: pd.DataFrame, top15: list, first_date: pd.Timestamp) -> dict:
    """
    Für jedes Top-15-Team die gültige (nicht-NaN, ELIM_DATE-begrenzte) Zeitreihe,
    als (Tage-seit-Start als float, Werte, Datumswerte) für die Interpolation.
    """
    series = {}
    for team in top15:
        tdf = df[df["Team"] == team].sort_values("Datum")
        tdf_valid = tdf[tdf["Wahrscheinlichkeit_Shin_in_Prozent"].notna()]
        if team in cpc.ELIM_DATE:
            tdf_valid = tdf_valid[tdf_valid["Datum"] <= cpc.ELIM_DATE[team]]
        days_arr   = (tdf_valid["Datum"] - first_date).dt.days.to_numpy(dtype=float)
        values_arr = tdf_valid["Wahrscheinlichkeit_Shin_in_Prozent"].to_numpy(dtype=float)
        dates_arr  = tdf_valid["Datum"].to_numpy()
        series[team] = (days_arr, values_arr, dates_arr)
    return series


def _interp_point(team_data: tuple, t_days: float):
    """Interpolierter (Tage, Wert) für ein Team zum aktuellen virtuellen Zeitpunkt.
    Gibt None zurück, falls das Team noch keine Daten hat; klemmt am letzten
    echten Datenpunkt (Ausscheiden), statt darüber hinaus flach weiterzulaufen."""
    days_arr, values_arr, _ = team_data
    if len(days_arr) == 0:
        return None
    t_clip = min(t_days, days_arr[-1])
    if t_clip < days_arr[0]:
        return None
    val = float(np.interp(t_clip, days_arr, values_arr))
    return t_clip, val


def build_animation(df: pd.DataFrame) -> None:
    top15 = cpc.select_top15(df)

    dates      = sorted(df["Datum"].unique())
    first_date = dates[0]
    last_date  = dates[-1]
    span_days  = (last_date - first_date).days
    dates_days = np.array([(d - first_date).days for d in dates], dtype=float)

    series = _prepare_team_series(df, top15, first_date)
    flag_cache = {team: cpc.get_flag(team) for team in top15}

    # ---- Finaler Zustand (identisch zu build_line_chart) für feste Achsen/Labels ----
    final_values    = np.array([series[t][1][-1] for t in top15])
    last_team_dates = [pd.Timestamp(series[t][2][-1]) for t in top15]
    y_max           = final_values.max()

    x_min = first_date - pd.Timedelta(days=span_days * 0.02)
    x_max = last_date + pd.Timedelta(days=span_days * 0.06)

    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
    plt.subplots_adjust(left=0.065, right=0.95, top=0.88, bottom=0.13)

    ylim_top_provisional = y_max * 1.18
    axes_height_pt = fig.get_size_inches()[1] * 72 * (0.88 - 0.10)
    pts_per_unit   = axes_height_pt / (ylim_top_provisional - min(0, final_values.min() - y_max * 0.03))
    min_gap        = 22 / pts_per_unit

    label_y = cpc.spread_label_positions(final_values, min_gap=min_gap)
    y_min_final = min(0, final_values.min() - y_max * 0.03, label_y.min() - min_gap * 0.6)
    y_max_final = max(ylim_top_provisional, label_y.max() + min_gap * 0.8)

    flag_x = last_date + pd.Timedelta(days=span_days * 0.035)
    needs_connector = np.abs(label_y - final_values) > min_gap * 0.15

    max_ticks = 20
    if len(dates) <= max_ticks:
        tick_dates = dates
    else:
        step = -(-len(dates) // max_ticks)
        tick_dates = dates[::step]
        if tick_dates[-1] != dates[-1]:
            tick_dates = tick_dates + [dates[-1]]

    wm_start       = pd.Timestamp(wm_paths.WM_START_DATE)
    wm_start_days  = (wm_start - first_date).days
    gp_ende_days   = (cpc.GRUPPENPHASE_ENDE - first_date).days

    # ---- Progressleiste oben: zeigt, wie weit die "Turniergeschichte" fortgeschritten ist ----
    ax_prog = fig.add_axes([0.065, 0.965, 0.885, 0.012])
    ax_prog.set_xlim(0, span_days)
    ax_prog.set_ylim(0, 1)
    ax_prog.axis("off")

    # ---- Frame-Zeitplan: gleichmäßige Zeitachse (in Tagen), keine Datum-Sprünge ----
    n_hold_start = int(round(HOLD_START_SECONDS * FPS))
    n_growth     = int(round(GROWTH_SECONDS * FPS))
    n_hold_end   = int(round(HOLD_END_SECONDS * FPS))
    n_total      = n_hold_start + n_growth + n_hold_end

    def frame_progress(idx: int) -> float:
        """Eased Fortschritt 0..1 über die Wachstumsphase (ruhiger Start/Ausklang)."""
        if idx < n_hold_start:
            return 0.0
        if idx >= n_hold_start + n_growth:
            return 1.0
        p = (idx - n_hold_start) / max(n_growth - 1, 1)
        return float(_ease_in_out_cubic(np.array(p)))

    def draw_frame(idx: int):
        q       = frame_progress(idx)
        t_days  = q * span_days
        blend   = _smoothstep(q, BLEND_START_FRACTION, 1.0)

        di = np.searchsorted(dates_days, t_days, side="right") - 1
        current_display_date = dates[max(di, 0)]

        ax.clear()

        for i, team in enumerate(top15):
            color = cpc.COLORS[i % len(cpc.COLORS)]
            pt = _interp_point(series[team], t_days)
            if pt is None:
                continue
            t_clip, val = pt

            days_arr, values_arr, dates_arr = series[team]
            mask = days_arr <= t_clip + 1e-9
            x_plot = list(dates_arr[mask])
            y_plot = list(values_arr[mask])

            on_real_point = mask.any() and abs(days_arr[mask][-1] - t_clip) < 1e-6
            cur_ts = first_date + pd.Timedelta(days=t_clip)
            if not on_real_point:
                x_plot.append(cur_ts)
                y_plot.append(val)

            ax.plot(x_plot, y_plot, linewidth=2.2, color=color, zorder=3, solid_capstyle="round")
            ax.plot(dates_arr[mask], values_arr[mask], marker="o", linestyle="None",
                     markersize=4.5, color=color, zorder=3)
            if not on_real_point:
                # Spitze der Linie: hebt den aktuellen "Zeichenstift"-Punkt hervor
                ax.plot([cur_ts], [val], marker="o", markersize=6.5, color=color,
                         markeredgecolor="white", markeredgewidth=0.9, zorder=4)

            final_ts = last_team_dates[i]
            blended_x = cur_ts + blend * (flag_x - cur_ts)
            blended_y = val + blend * (label_y[i] - val)

            if needs_connector[i] and blend > 0.02:
                ax.plot([final_ts if blend > 0.98 else cur_ts, blended_x],
                        [final_values[i] if blend > 0.98 else val, blended_y],
                        color=color, linewidth=0.8, alpha=blend * 0.5, zorder=2)

            ab = AnnotationBbox(
                OffsetImage(flag_cache[team], zoom=0.135), (blended_x, blended_y),
                frameon=False, box_alignment=(0, 0.5), annotation_clip=False,
            )
            ax.add_artist(ab)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min_final, y_max_final)

        wm_alpha = _smoothstep(t_days, wm_start_days, wm_start_days + REFLINE_FADE_DAYS)
        if 0 < wm_start_days <= span_days and wm_alpha > 0:
            ax.axvline(wm_start, color="#888888", linewidth=1.2, linestyle="--", zorder=2, alpha=wm_alpha)
            ax.text(wm_start + pd.Timedelta(days=span_days * 0.008),
                    ax.get_ylim()[1] * 0.985,
                    "WM-Start", fontsize=8.5, color="#666666", va="top", alpha=wm_alpha)

        gp_alpha = _smoothstep(t_days, gp_ende_days, gp_ende_days + REFLINE_FADE_DAYS)
        if 0 < gp_ende_days <= span_days and gp_alpha > 0:
            ax.axvline(cpc.GRUPPENPHASE_ENDE, color="#888888", linewidth=1.2, linestyle="--", zorder=2, alpha=gp_alpha)
            ax.text(cpc.GRUPPENPHASE_ENDE + pd.Timedelta(days=span_days * 0.008),
                    ax.get_ylim()[1] * 0.985,
                    "Vorrunde Ende", fontsize=8.5, color="#666666", va="top", alpha=gp_alpha)

        ax.set_ylabel("SProbability of Winning (%)", fontsize=11)
        ax.set_xlabel("Date", fontsize=11)
        ax.set_title(
            f"Changes Over Time in the Top 15 Probabilities of Winning\n"
            f"Status: {current_display_date.strftime('%d.%m.%Y')}",
            fontsize=14, fontweight="bold", color="#2C3E50", pad=14,
        )

        ax.set_xticks(tick_dates)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d.%m."))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9.5)
        ax.tick_params(axis="y", labelsize=9.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
        ax.grid(color="#E8E8E8", zorder=0)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        # ---- Progressleiste: Gesamtfortschritt der Turniergeschichte ----
        ax_prog.clear()
        ax_prog.set_xlim(0, span_days)
        ax_prog.set_ylim(0, 1)
        ax_prog.axis("off")
        ax_prog.plot([0, span_days], [0.5, 0.5], color="#E0E0E0", linewidth=5,
                     solid_capstyle="round", zorder=1)
        ax_prog.plot([0, t_days], [0.5, 0.5], color="#457B9D", linewidth=5,
                     solid_capstyle="round", zorder=2)
        for marker_day in (wm_start_days, gp_ende_days):
            if 0 < marker_day <= span_days:
                ax_prog.plot([marker_day], [0.5], marker="|", markersize=10,
                             markeredgewidth=1.6, color="#888888", zorder=3)

        fig.texts.clear()
        fig.text(0.02, 0.02,
                 "Institute of Exercise Training and Sport Informatics · Lukas Gardeweg, Fabian Wunderlich und Daniel Memmert",
                 fontsize=10, color="#000000")

    anim = FuncAnimation(fig, draw_frame, frames=n_total, blit=False)
    writer = FFMpegWriter(fps=FPS, bitrate=2400)
    anim.save(OUTPUT, writer=writer)
    plt.close(fig)
    print(f"Gespeichert: {OUTPUT}")


def main():
    _check_ffmpeg()
    df = cpc.load_data()
    missing = set(df["Team"].unique()) - set(cpc.FLAG_CODES)
    if missing:
        raise ValueError(f"Keine Flaggen-Zuordnung für: {missing}")

    print("Erzeuge animierten Zeitverlauf (Top 15)...")
    build_animation(df)


if __name__ == "__main__":
    main()
