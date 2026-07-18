# -*- coding: utf-8 -*-
"""
create_line_chart_animation_reel.py
Vertikale (9:16, 1080x1920) Instagram-Reel-Version des animierten Top-15-
Zeitverlaufs. Unterschiede zur Breitbild-Version (create_line_chart_animation.py):

  - Kein datumsabhängiger Chart-Titel, stattdessen eine große, dauerhaft
    sichtbare Branding-Kopfzeile (Institut + Autoren) – auf einen Blick klar,
    von wem die Grafik stammt.
  - Größere Schrift, dickere Linien, größere Flaggen und Prozentzahlen neben
    den Flaggen – für die Betrachtung auf dem Handy optimiert.
  - Gleiche Wachstums-/Timing-Logik wie die Breitbild-Version (wird von dort
    importiert), damit beide Versionen synchron wirken.

Benötigt ffmpeg im PATH (für MP4-Export über matplotlib).

Verwendung: python create_line_chart_animation_reel.py
"""

import os
import sys

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import create_png_charts as cpc
from create_line_chart_animation import (
    FPS, HOLD_START_SECONDS, GROWTH_SECONDS, HOLD_END_SECONDS,
    BLEND_START_FRACTION, REFLINE_FADE_DAYS,
    _check_ffmpeg, _ease_in_out_cubic, _smoothstep,
    _prepare_team_series, _interp_point,
)

ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import wm_paths

OUTPUT = os.path.join(BASE, "wm2026_zeitverlauf_top15_animation_reel.mp4")

BRAND_COLOR = "#2C3E50"
ACCENT_COLOR = "#457B9D"


def build_animation(df: pd.DataFrame) -> None:
    top15 = cpc.select_top15(df)

    dates      = sorted(df["Datum"].unique())
    first_date = dates[0]
    last_date  = dates[-1]
    span_days  = (last_date - first_date).days
    dates_days = np.array([(d - first_date).days for d in dates], dtype=float)

    series = _prepare_team_series(df, top15, first_date)
    flag_cache = {team: cpc.get_flag(team) for team in top15}

    final_values    = np.array([series[t][1][-1] for t in top15])
    last_team_dates = [pd.Timestamp(series[t][2][-1]) for t in top15]
    y_max           = final_values.max()

    # ---- Vertikales 9:16-Format (1080x1920 bei dpi=120) ----
    fig = plt.figure(figsize=(9, 16), dpi=120, facecolor="white")

    # Kopfzeile: große Branding-Fläche – Institut + Autoren, dauerhaft sichtbar
    ax_banner = fig.add_axes([0, 0.918, 1, 0.082])
    ax_banner.set_xlim(0, 1); ax_banner.set_ylim(0, 1); ax_banner.axis("off")
    ax_banner.add_patch(Rectangle((0, 0), 1, 1, transform=ax_banner.transAxes,
                                    facecolor=BRAND_COLOR, zorder=0))
    ax_banner.text(0.5, 0.66, "INSTITUT FÜR TRAININGSWISSENSCHAFT\nUND SPORTINFORMATIK",
                   ha="center", va="center", fontsize=20, fontweight="bold",
                   color="white", linespacing=1.35, zorder=1)
    ax_banner.text(0.5, 0.20, "Lukas Gardeweg  ·  Fabian Wunderlich  ·  Daniel Memmert",
                   ha="center", va="center", fontsize=12.5, color="#C9D6E3", zorder=1)

    # Subtitle: kurzer, statischer Kontext (kein datumsabhängiger Titel mehr)
    ax_sub = fig.add_axes([0, 0.880, 1, 0.034])
    ax_sub.set_xlim(0, 1); ax_sub.set_ylim(0, 1); ax_sub.axis("off")
    ax_sub.text(0.5, 0.5, "WM 2026  ·  Siegwahrscheinlichkeiten der Top 15 im Zeitverlauf",
                ha="center", va="center", fontsize=15, fontweight="bold", color=BRAND_COLOR)

    # Fortschrittsleiste + aktuelles Datum
    ax_prog = fig.add_axes([0.09, 0.860, 0.82, 0.010])
    date_tag_y = 0.848

    # Hauptchart
    CHART_LEFT, CHART_RIGHT = 0.15, 0.76
    ax = fig.add_axes([CHART_LEFT, 0.095, CHART_RIGHT - CHART_LEFT, 0.745])

    # Untere Akzentleiste (visueller Rahmen/Symmetrie zur Kopfzeile)
    ax_footer = fig.add_axes([0, 0, 1, 0.012])
    ax_footer.set_xlim(0, 1); ax_footer.set_ylim(0, 1); ax_footer.axis("off")
    ax_footer.add_patch(Rectangle((0, 0), 1, 1, transform=ax_footer.transAxes,
                                    facecolor=BRAND_COLOR, zorder=0))

    ylim_top_provisional = y_max * 1.18
    axes_height_pt = fig.get_size_inches()[1] * 72 * 0.745
    pts_per_unit   = axes_height_pt / (ylim_top_provisional - min(0, final_values.min() - y_max * 0.03))
    min_gap        = 30 / pts_per_unit

    label_y = cpc.spread_label_positions(final_values, min_gap=min_gap)
    y_min_final = min(0, final_values.min() - y_max * 0.03, label_y.min() - min_gap * 0.6)
    y_max_final = max(ylim_top_provisional, label_y.max() + min_gap * 0.8)

    x_min = first_date - pd.Timedelta(days=span_days * 0.03)
    x_max = last_date + pd.Timedelta(days=span_days * 0.14)
    flag_x = last_date + pd.Timedelta(days=span_days * 0.05)
    needs_connector = np.abs(label_y - final_values) > min_gap * 0.15

    max_ticks = 9
    if len(dates) <= max_ticks:
        tick_dates = dates
    else:
        step = -(-len(dates) // max_ticks)
        tick_dates = dates[::step]
        if tick_dates[-1] != dates[-1]:
            tick_dates = tick_dates + [dates[-1]]

    wm_start      = pd.Timestamp(wm_paths.WM_START_DATE)
    wm_start_days = (wm_start - first_date).days
    gp_ende_days  = (cpc.GRUPPENPHASE_ENDE - first_date).days

    n_hold_start = int(round(HOLD_START_SECONDS * FPS))
    n_growth     = int(round(GROWTH_SECONDS * FPS))
    n_hold_end   = int(round(HOLD_END_SECONDS * FPS))
    n_total      = n_hold_start + n_growth + n_hold_end

    def frame_progress(idx: int) -> float:
        if idx < n_hold_start:
            return 0.0
        if idx >= n_hold_start + n_growth:
            return 1.0
        p = (idx - n_hold_start) / max(n_growth - 1, 1)
        return float(_ease_in_out_cubic(np.array(p)))

    def draw_frame(idx: int):
        q      = frame_progress(idx)
        t_days = q * span_days
        blend  = _smoothstep(q, BLEND_START_FRACTION, 1.0)

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

            ax.plot(x_plot, y_plot, linewidth=3.0, color=color, zorder=3, solid_capstyle="round")
            ax.plot(dates_arr[mask], values_arr[mask], marker="o", linestyle="None",
                     markersize=5.5, color=color, zorder=3)
            if not on_real_point:
                ax.plot([cur_ts], [val], marker="o", markersize=8.5, color=color,
                         markeredgecolor="white", markeredgewidth=1.1, zorder=4)

            final_ts = last_team_dates[i]
            blended_x = cur_ts + blend * (flag_x - cur_ts)
            blended_y = val + blend * (label_y[i] - val)

            if needs_connector[i] and blend > 0.02:
                ax.plot([final_ts if blend > 0.98 else cur_ts, blended_x],
                        [final_values[i] if blend > 0.98 else val, blended_y],
                        color=color, linewidth=1.0, alpha=blend * 0.5, zorder=2)

            ab = AnnotationBbox(
                OffsetImage(flag_cache[team], zoom=0.22), (blended_x, blended_y),
                frameon=False, box_alignment=(0, 0.5), annotation_clip=False,
            )
            ax.add_artist(ab)

            if blend > 0.1:
                ax.annotate(f"{val:.1f}%".replace(".", ","),
                            xy=(blended_x, blended_y), xytext=(30, 0),
                            textcoords="offset points", va="center", ha="left",
                            fontsize=12.5, fontweight="bold", color=color,
                            alpha=min(blend * 1.4, 1.0), zorder=4, annotation_clip=False)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min_final, y_max_final)

        wm_alpha = _smoothstep(t_days, wm_start_days, wm_start_days + REFLINE_FADE_DAYS)
        if 0 < wm_start_days <= span_days and wm_alpha > 0:
            ax.axvline(wm_start, color="#999999", linewidth=1.4, linestyle="--", zorder=2, alpha=wm_alpha)
            ax.text(wm_start + pd.Timedelta(days=span_days * 0.012),
                    y_min_final + (y_max_final - y_min_final) * 0.985,
                    "WM-Start", fontsize=10.5, color="#666666", va="top", alpha=wm_alpha)

        gp_alpha = _smoothstep(t_days, gp_ende_days, gp_ende_days + REFLINE_FADE_DAYS)
        if 0 < gp_ende_days <= span_days and gp_alpha > 0:
            ax.axvline(cpc.GRUPPENPHASE_ENDE, color="#999999", linewidth=1.4, linestyle="--", zorder=2, alpha=gp_alpha)
            ax.text(cpc.GRUPPENPHASE_ENDE + pd.Timedelta(days=span_days * 0.012),
                    y_min_final + (y_max_final - y_min_final) * 0.925,
                    "Vorrunde Ende", fontsize=10.5, color="#666666", va="top", alpha=gp_alpha)

        ax.set_ylabel("Siegwahrscheinlichkeit (%)", fontsize=14)
        ax.set_xticks(tick_dates)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d.%m."))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=12.5)
        ax.tick_params(axis="y", labelsize=12.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
        ax.grid(color="#E8E8E8", zorder=0)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        # ---- Fortschrittsleiste + Datumsanzeige ----
        ax_prog.clear()
        ax_prog.set_xlim(0, span_days); ax_prog.set_ylim(0, 1); ax_prog.axis("off")
        ax_prog.plot([0, span_days], [0.5, 0.5], color="#E0E0E0", linewidth=6,
                     solid_capstyle="round", zorder=1)
        ax_prog.plot([0, t_days], [0.5, 0.5], color=ACCENT_COLOR, linewidth=6,
                     solid_capstyle="round", zorder=2)
        for marker_day in (wm_start_days, gp_ende_days):
            if 0 < marker_day <= span_days:
                ax_prog.plot([marker_day], [0.5], marker="|", markersize=12,
                             markeredgewidth=2.0, color="#888888", zorder=3)

        for t in fig.texts:
            if getattr(t, "_is_date_tag", False):
                t.remove()
        date_tag = fig.text(0.91, date_tag_y, current_display_date.strftime("%d.%m.%Y"),
                            ha="right", va="center", fontsize=12, color="#666666")
        date_tag._is_date_tag = True

    anim = FuncAnimation(fig, draw_frame, frames=n_total, blit=False)
    writer = FFMpegWriter(fps=FPS, bitrate=3200)
    anim.save(OUTPUT, writer=writer)
    plt.close(fig)
    print(f"Gespeichert: {OUTPUT}")


def main():
    _check_ffmpeg()
    df = cpc.load_data()
    missing = set(df["Team"].unique()) - set(cpc.FLAG_CODES)
    if missing:
        raise ValueError(f"Keine Flaggen-Zuordnung für: {missing}")

    print("Erzeuge animierten Zeitverlauf (Top 15, Reel-Format)...")
    build_animation(df)


if __name__ == "__main__":
    main()
