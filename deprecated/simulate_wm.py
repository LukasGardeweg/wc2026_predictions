import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import os

# ── Daten laden ──────────────────────────────────────────────────────────────
BASE = r'C:\Users\Acer\DOCUME~1\DOKUME~1\INSTIT~1\WMPROG~1'
df = pd.read_excel(os.path.join(BASE, 'processed_data.xlsx'))
df.columns = df.columns.str.strip()
df['Datum'] = pd.to_datetime(df['Datum'])

last_date = df['Datum'].max()
top15 = (df[df['Datum'] == last_date]
         .sort_values('Wahrscheinlichkeit_in_Prozent', ascending=False)
         .head(15)['Team'].tolist())

df_top = df[df['Team'].isin(top15)].copy()
pivot_real = df_top.pivot(index='Datum', columns='Team',
                          values='Wahrscheinlichkeit_in_Prozent')
pivot_real = pivot_real[top15]

# ── Simulation ────────────────────────────────────────────────────────────────
# Datenpunkte der Simulation
sim_dates = [
    pd.Timestamp('2026-06-11'),  # WM Beginn
    pd.Timestamp('2026-06-25'),  # Mitte Gruppenphase
    pd.Timestamp('2026-07-02'),  # Ende Gruppenphase
    pd.Timestamp('2026-07-08'),  # Nach Achtelfinale  (Spanien & Norwegen raus)
    pd.Timestamp('2026-07-13'),  # Nach Viertelfinale (Deutschland & Kolumbien & Marokko raus)
]

# Szenario:
#   Gruppenphase-Aus:   Uruguay, Belgien
#   Achtelfinale-Aus:   Spanien, Norwegen
#   Viertelfinale-Aus:  Deutschland, Kolumbien, Marokko
#   Verbleibend:        Frankreich, England, Brasilien, Argentinien,
#                       Portugal, Niederlande, Japan, USA
sim_vals = {
    #                    Jun11  Jun25  Jul02  Jul08  Jul13
    'Spanien':     [     15.2,  18.0,  19.0,   0.0,   0.0],  # Achtelfinale raus
    'Frankreich':  [     14.5,  16.0,  17.0,  22.5,  26.0],
    'England':     [     11.5,  12.5,  13.0,  17.5,  21.0],
    'Brasilien':   [      9.3,  11.5,  12.5,  16.0,  20.0],
    'Argentinien': [      9.1,   8.5,   8.8,  12.0,  15.5],
    'Portugal':    [      7.3,   8.0,   8.5,  11.0,  13.5],
    'Deutschland': [      6.0,   6.5,   7.0,   8.5,   0.0],  # Viertelfinale raus
    'Niederlande': [      4.0,   4.5,   5.0,   6.0,   7.5],
    'Norwegen':    [      2.7,   2.0,   1.5,   0.0,   0.0],  # Achtelfinale raus
    'Belgien':     [      2.2,   1.8,   0.0,   0.0,   0.0],  # Gruppenphase raus
    'Kolumbien':   [      2.1,   2.0,   2.5,   3.0,   0.0],  # Viertelfinale raus
    'Japan':       [      1.7,   3.2,   3.8,   4.5,   5.5],  # Überraschungsteam
    'Marokko':     [      1.6,   1.8,   2.0,   2.5,   0.0],  # Viertelfinale raus
    'USA':         [      1.4,   2.2,   2.8,   3.5,   4.0],  # Heimvorteil
    'Uruguay':     [      1.1,   0.7,   0.0,   0.0,   0.0],  # Gruppenphase raus
}

# Vertikale Markierungslinien
vlines = {
    'WM Beginn\n11.06.': pd.Timestamp('2026-06-11'),
    'Ende Gruppen-\nphase  02.07.': pd.Timestamp('2026-07-02'),
    'Achtelfinale\n04.07.': pd.Timestamp('2026-07-04'),
    'Viertelfinale\n09.07.': pd.Timestamp('2026-07-09'),
}

# ── Farben (gleiche Reihenfolge wie vorher) ────────────────────────────────
colors = [
    '#E63946', '#457B9D', '#2A9D8F', '#E9C46A', '#F4A261',
    '#264653', '#A8DADC', '#6D6875', '#B5838D', '#CC0000',
    '#80B918', '#3A0CA3', '#F72585', '#009999', '#7B2D8B'
]

# ── Figure ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(24, 12))
fig.patch.set_facecolor('#F8F9FA')
ax.set_facecolor('#F8F9FA')

dates_real = sorted(df['Datum'].unique())

# ── Reale Linien (durchgezogen) ───────────────────────────────────────────────
for i, team in enumerate(top15):
    vals = pivot_real[team].dropna()
    ax.plot(vals.index, vals.values,
            color=colors[i], linewidth=2.3, marker='o', markersize=5,
            zorder=4, solid_capstyle='round')

# ── Simulationslinien (gestrichelt) ──────────────────────────────────────────
for i, team in enumerate(top15):
    last_real_val = pivot_real[team].dropna().iloc[-1]
    sv = sim_vals.get(team, [last_real_val] * len(sim_dates))
    sim_x = [last_date] + sim_dates
    sim_y = [last_real_val] + sv

    # Linie segmentiert zeichnen: bis zur Elimination voll, danach nichts
    # (Elimination = 0-Wert markiert den Austritt)
    seg_x, seg_y = [sim_x[0]], [sim_y[0]]
    for j in range(1, len(sim_x)):
        seg_x.append(sim_x[j])
        seg_y.append(sim_y[j])
        if sim_y[j] == 0.0 and j > 0 and sim_y[j-1] > 0.0:
            # Elimination: Punkt zeichnen, dann aufhören
            ax.plot(seg_x, seg_y,
                    color=colors[i], linewidth=2.3, marker='o', markersize=5,
                    linestyle='--', zorder=4, alpha=0.88, dash_capstyle='round')
            # X-Marker an Eliminationspunkt
            ax.plot(sim_x[j], 0, marker='x', color=colors[i],
                    markersize=10, markeredgewidth=2.5, zorder=5)
            seg_x, seg_y = [], []
            break

    if seg_x:  # falls nicht eliminiert (noch Werte übrig)
        ax.plot(seg_x, seg_y,
                color=colors[i], linewidth=2.3, marker='o', markersize=5,
                linestyle='--', zorder=4, alpha=0.88, dash_capstyle='round')

# ── Vertikale Phasenlinien ────────────────────────────────────────────────────
y_max = ax.get_ylim()[1] if ax.get_ylim()[1] > 5 else 28
for label, date in vlines.items():
    ax.axvline(x=date, color='#444444', linestyle=':', linewidth=1.8,
               alpha=0.65, zorder=2)
    ax.text(date, y_max * 0.985, label,
            ha='center', va='top', fontsize=8.5, color='#333333',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                      edgecolor='#AAAAAA', alpha=0.85))

# ── Elimination-Annotationen ──────────────────────────────────────────────────
elimination_events = {
    'Uruguay\nraus':   (pd.Timestamp('2026-07-02'), 'Uruguay',   '#7B2D8B'),
    'Belgien\nraus':   (pd.Timestamp('2026-07-02'), 'Belgien',   '#CC0000'),
    'Spanien\nraus':   (pd.Timestamp('2026-07-08'), 'Spanien',   '#E63946'),
    'Norwegen\nraus':  (pd.Timestamp('2026-07-08'), 'Norwegen',  '#6D6875'),
    'Deutsch-\nland\nraus': (pd.Timestamp('2026-07-13'), 'Deutschland', '#A8DADC'),
}

# ── Team-Labels rechts ────────────────────────────────────────────────────────
last_sim_date = sim_dates[-1]
label_info = []
for i, team in enumerate(top15):
    sv = sim_vals.get(team, [])
    final_val = sv[-1] if sv else pivot_real[team].dropna().iloc[-1]
    if final_val > 0:
        label_info.append({'val': final_val, 'ci': i, 'team': team})

label_info.sort(key=lambda x: x['val'], reverse=True)

min_gap = 0.65
adj_ys = []
for idx, info in enumerate(label_info):
    if idx == 0:
        adj_ys.append(info['val'])
    else:
        prev = adj_ys[-1]
        proposed = info['val']
        if prev - proposed < min_gap:
            proposed = prev - min_gap
        adj_ys.append(proposed)

label_x = last_sim_date + pd.Timedelta(days=1.5)
for idx, info in enumerate(label_info):
    team = info['team']
    val = info['val']
    ci = info['ci']
    adj_y = adj_ys[idx]
    ax.annotate(
        f"{team}  {val:.1f}%",
        xy=(last_sim_date, val),
        xytext=(label_x, adj_y),
        textcoords='data',
        va='center', ha='left',
        fontsize=9, color=colors[ci], fontweight='bold',
        annotation_clip=False,
        arrowprops=dict(arrowstyle='-', color=colors[ci],
                        lw=0.9, alpha=0.55) if abs(adj_y - val) > 0.05 else None
    )

# ── Achsen & Formatierung ─────────────────────────────────────────────────────
all_dates = dates_real + sim_dates
ax.set_xlim(dates_real[0] - pd.Timedelta(days=2),
            last_sim_date + pd.Timedelta(days=22))

ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='gray', zorder=0)
ax.set_axisbelow(True)

# X-Achse: echte Daten + Sim-Daten als Ticks
tick_dates = dates_real + sim_dates
tick_labels = [d.strftime('%d.%m.') for d in tick_dates]
ax.set_xticks(tick_dates)
ax.set_xticklabels(tick_labels, rotation=35, ha='right', fontsize=9)

ax.set_ylabel('Siegwahrscheinlichkeit (%)', fontsize=12, labelpad=10)
ax.set_xlabel('Datum', fontsize=12, labelpad=10)
ax.set_title(
    'WM 2026 – Zeitliche Entwicklung der Siegwahrscheinlichkeiten (Top 15)\n'
    'Reale Wettquoten (25.03.–13.05.2026) + Turniersimulation (ab 11.06.2026)',
    fontsize=14, fontweight='bold', pad=22)

for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0f}%'))

# ── Legende: Real vs. Simulation ─────────────────────────────────────────────
legend_elements = [
    Line2D([0], [0], color='gray', linewidth=2.2, linestyle='-',
           marker='o', markersize=5, label='Reale Wettquoten'),
    Line2D([0], [0], color='gray', linewidth=2.2, linestyle='--',
           marker='o', markersize=5, label='Simulation (hypothetisch)'),
    Line2D([0], [0], color='gray', linewidth=0, marker='x',
           markersize=9, markeredgewidth=2.5, label='Ausscheiden'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=9,
          framealpha=0.85, edgecolor='#CCCCCC')

# ── Quellhinweis ──────────────────────────────────────────────────────────────
fig.text(0.01, 0.01,
         'Reale Daten: Oddspedia / Oddschecker  |  Simulation: hypothetisches Turnierszenario  |  Institut für Sportinformatik',
         fontsize=7.5, color='gray', style='italic')

# ── Trennlinie Real/Simulation ────────────────────────────────────────────────
ax.axvline(x=last_date + pd.Timedelta(days=3), color='#999999',
           linestyle='-', linewidth=1, alpha=0.4, zorder=1)
ax.text(last_date + pd.Timedelta(days=4), ax.get_ylim()[0] + 0.3,
        '◀ real  |  Simulation ▶',
        fontsize=7.5, color='#888888', va='bottom')

plt.tight_layout(rect=[0, 0.03, 0.84, 1])
out = os.path.join(BASE, 'wm2026_simulation_top15.png')
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved: {out}')
plt.close()
