# -*- coding: utf-8 -*-
"""
create_visualization.py
Erzeugt wm2026_probabilities.html mit:
  - Interaktiver Zeitverlauf-Visualisierung (Plotly)
  - Datenkontrolle-Section (Troubleshooting, Long-Format, Wide-Format)

Verwendung: python create_visualization.py
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go

import wm_paths
from update_processed_data import build_wide_format

OUTCOMES = ["Heimsieg", "Unentschieden", "Heimniederlage"]

BASE                = os.path.dirname(os.path.abspath(__file__))
PRE_WM_LONG_FILE    = os.path.join(BASE, "processed_data_pre_wm", "processed_data_long.xlsx")
DURING_WM_LONG_FILE = os.path.join(BASE, "processed_data_during_wm", "processed_data_long.xlsx")
DURING_WM_FILE      = os.path.join(BASE, "Einzelspielprognosen", "processed_match_predictions.xlsx")
OUTPUT_FILE         = os.path.join(BASE, "wm2026_probabilities.html")

COLORS = [
    "#E63946", "#457B9D", "#2A9D8F", "#E9C46A", "#F4A261",
    "#264653", "#6D6875", "#B5838D", "#CC0000", "#80B918",
    "#3A0CA3", "#F72585", "#009999", "#7B2D8B", "#FF6B35",
]


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
    if "Team" not in df.columns or "Datum" not in df.columns:
        return None
    df["Datum"] = pd.to_datetime(df["Datum"])
    df["Team"]  = df["Team"].astype(str).str.strip()
    return df


def load_data():
    """
    Lädt die Zeitreihe der WM-Sieger-Wahrscheinlichkeiten als durchgehende
    Zeitlinie: pre_wm-Snapshots (vor WM-Start) + during_wm-Snapshots
    (ab 11.06.2026, sobald vorhanden), nach Datum sortiert.
    """
    df = _load_long(PRE_WM_LONG_FILE)
    df_during = _load_long(DURING_WM_LONG_FILE)
    if df_during is not None and not df_during.empty:
        df = pd.concat([df, df_during], ignore_index=True)
    return df.sort_values("Datum").reset_index(drop=True)


def load_wide(df):
    """Baut das Wide-Format direkt aus der (kombinierten) Zeitreihe."""
    return build_wide_format(df)


def rank_teams(df):
    latest = df["Datum"].max()
    return (
        df[df["Datum"] == latest]
        .sort_values("Wahrscheinlichkeit_Shin", ascending=False)
        ["Team"].tolist()
    )


def load_during_wm_data():
    """Lädt die Einzelspiel-Prognosen (Snapshot, kein Zeitverlauf). None falls noch nicht erzeugt."""
    if not os.path.exists(DURING_WM_FILE):
        return None
    df = pd.read_excel(DURING_WM_FILE)
    df.columns = df.columns.str.strip()
    return df


# ---------------------------------------------------------------------------
# Troubleshooting / Datenkontrolle
# ---------------------------------------------------------------------------

def run_checks(df_long, df_wide):
    """Gibt (snapshot_checks, global_checks) zurück."""

    snapshot_checks = []
    for datum, grp in df_long.sort_values("Datum").groupby("Datum", sort=True):
        s_norm = grp["Wahrscheinlichkeit_in_Prozent"].sum()
        s_shin = grp["Wahrscheinlichkeit_Shin_in_Prozent"].sum()
        n      = len(grp)

        def status(val, target=100.0, tol_ok=0.05, tol_warn=0.1):
            diff = abs(val - target)
            return "ok" if diff < tol_ok else ("warn" if diff < tol_warn else "err")

        snapshot_checks.append({
            "Datum":        datum.strftime("%d.%m.%Y"),
            "Teams":        n,
            "teams_status": "ok" if n == 48 else "err",
            "norm_sum":     round(s_norm, 4),
            "norm_status":  status(s_norm),
            "shin_sum":     round(s_shin, 4),
            "shin_status":  status(s_shin),
        })

    global_checks = []

    # Duplikate
    dupes = df_long[df_long.duplicated(["Team", "Datum"], keep=False)]
    global_checks.append({
        "check":  "Duplikate (Team + Datum)",
        "wert":   "Keine" if dupes.empty else f"{len(dupes)} Zeilen",
        "status": "ok" if dupes.empty else "err",
    })

    # Fehlende Kernwerte
    core = ["Durchsch_Quote", "Wahrscheinlichkeit_in_Prozent", "Wahrscheinlichkeit_Shin_in_Prozent"]
    nulls = df_long[core].isnull().sum().sum()
    global_checks.append({
        "check":  "Fehlende Werte (Quote / Wahrsch.)",
        "wert":   "Keine" if nulls == 0 else f"{nulls} Werte",
        "status": "ok" if nulls == 0 else "err",
    })

    # Quoten-Plausibilität
    min_q    = df_long["Durchsch_Quote"].min()
    max_q    = df_long["Durchsch_Quote"].max()
    min_team = df_long.loc[df_long["Durchsch_Quote"].idxmin(), "Team"]
    max_team = df_long.loc[df_long["Durchsch_Quote"].idxmax(), "Team"]
    global_checks.append({
        "check":  "Quote Min (Favorit)",
        "wert":   f"{min_q:.2f}  ({min_team})",
        "status": "ok" if min_q > 1.0 else "err",
    })
    global_checks.append({
        "check":  "Quote Max (Außenseiter)",
        "wert":   f"{max_q:.2f}  ({max_team})",
        "status": "ok",
    })

    # Wide ↔ Long Konsistenz
    snapshots   = sorted(df_long["Datum"].unique())
    mismatches  = 0
    for i, datum in enumerate(snapshots, start=1):
        snap = df_long[df_long["Datum"] == datum].set_index("Team")
        for _, row in df_wide.iterrows():
            team = row["Team"]
            if team not in snap.index:
                mismatches += 1
                continue
            shin_col = f"Shin_Wahrscheinlichkeit_in_Prozent_{i}"
            if shin_col in row and not pd.isna(row[shin_col]):
                if abs(row[shin_col] - round(snap.loc[team, "Wahrscheinlichkeit_Shin_in_Prozent"], 2)) > 0.005:
                    mismatches += 1
    global_checks.append({
        "check":  "Wide ↔ Long Konsistenz",
        "wert":   "Alle Werte stimmen überein" if mismatches == 0 else f"{mismatches} Abweichungen",
        "status": "ok" if mismatches == 0 else "err",
    })

    return snapshot_checks, global_checks


def build_inspection_section(df_long, df_wide):
    """Erzeugt den HTML-Block mit drei Tabs: Troubleshooting, Long, Wide."""

    snapshot_checks, global_checks = run_checks(df_long, df_wide)
    n_zeitpunkte = (len(df_wide.columns) - 1) // 4

    # Long-Format für JSON vorbereiten
    long_disp = df_long[[
        "Team", "Datum",
        "Durchsch_Quote",
        "Wahrscheinlichkeit_in_Prozent",
        "Wahrscheinlichkeit_Shin_in_Prozent",
    ]].copy()
    long_disp["Datum"]                           = long_disp["Datum"].dt.strftime("%d.%m.%Y")
    long_disp["Durchsch_Quote"]                  = long_disp["Durchsch_Quote"].round(2)
    long_disp["Wahrscheinlichkeit_in_Prozent"]   = long_disp["Wahrscheinlichkeit_in_Prozent"].round(2)
    long_disp["Wahrscheinlichkeit_Shin_in_Prozent"] = long_disp["Wahrscheinlichkeit_Shin_in_Prozent"].round(2)
    long_disp = long_disp.rename(columns={
        "Durchsch_Quote":                     "Quote",
        "Wahrscheinlichkeit_in_Prozent":      "Norm_%",
        "Wahrscheinlichkeit_Shin_in_Prozent": "Shin_%",
    })
    long_json = long_disp.to_json(orient="records", force_ascii=False)

    # Wide-Format für JSON vorbereiten
    wide_prep = df_wide.copy()
    for col in wide_prep.columns:
        if pd.api.types.is_float_dtype(wide_prep[col]):
            wide_prep[col] = wide_prep[col].round(2)
    wide_cols_json = json.dumps(wide_prep.columns.tolist(), ensure_ascii=False)
    wide_rows_json = wide_prep.where(pd.notnull(wide_prep), None).to_json(
        orient="values", force_ascii=False
    )

    datums_json        = json.dumps(sorted(long_disp["Datum"].unique().tolist()), ensure_ascii=False)
    snap_checks_json   = json.dumps(snapshot_checks,  ensure_ascii=False)
    global_checks_json = json.dumps(global_checks,    ensure_ascii=False)

    return f"""
<div class="inspection-section">
  <div class="inspection-title">&#128202; Datenkontrolle</div>
  <div class="insp-tab-bar">
    <button class="insp-tab-btn active" onclick="showInspTab(this,'checks')">Troubleshooting</button>
    <button class="insp-tab-btn"        onclick="showInspTab(this,'long')">Long-Format</button>
    <button class="insp-tab-btn"        onclick="showInspTab(this,'wide')">Wide-Format</button>
  </div>

  <!-- TAB: Troubleshooting -->
  <div id="insp-tab-checks" class="insp-tab-content active">
    <p style="font-size:11.5px;color:#999;margin:0 0 12px">Automatische Plausibilitätsprüfung. Grün = OK, Gelb = kleiner Rundfehler (&lt;0.1 PP), Rot = Fehler.</p>
    <div style="display:flex;gap:30px;flex-wrap:wrap;align-items:flex-start;">
      <div>
        <div class="check-section-title">Pro Snapshot</div>
        <table class="check-table" id="snap-check-table"></table>
      </div>
      <div>
        <div class="check-section-title">Globale Checks</div>
        <table class="check-table" id="global-check-table"></table>
      </div>
    </div>
  </div>

  <!-- TAB: Long-Format -->
  <div id="insp-tab-long" class="insp-tab-content">
    <div class="filter-row">
      <span class="filter-label">Snapshot:</span>
      <select class="filter-select" id="long-datum-filter" onchange="renderLongTable()"></select>
      <span class="table-info" id="long-info"></span>
    </div>
    <div class="data-table-wrap">
      <table class="data-table" id="long-table"></table>
    </div>
  </div>

  <!-- TAB: Wide-Format -->
  <div id="insp-tab-wide" class="insp-tab-content">
    <div class="filter-row">
      <span class="table-info">48 Teams &times; {n_zeitpunkte} Zeitpunkte &nbsp;&bull;&nbsp; je Zeitpunkt: Datum, Ø Quote, Norm %, Shin % &nbsp;&bull;&nbsp; horizontal scrollbar</span>
    </div>
    <div class="data-table-wrap">
      <table class="data-table" id="wide-table"></table>
    </div>
  </div>
</div>

<script>
(function() {{
var SNAP_CHECKS   = {snap_checks_json};
var GLOBAL_CHECKS = {global_checks_json};
var LONG_DATA     = {long_json};
var WIDE_COLS     = {wide_cols_json};
var WIDE_ROWS     = {wide_rows_json};
var DATUMS        = {datums_json};

// --- Tab switching ---
window.showInspTab = function(btn, id) {{
  document.querySelectorAll('.insp-tab-content').forEach(function(el) {{ el.classList.remove('active'); }});
  document.querySelectorAll('.insp-tab-btn').forEach(function(el) {{ el.classList.remove('active'); }});
  document.getElementById('insp-tab-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'long'  && !document.getElementById('long-datum-filter').options.length) initLongTab();
  if (id === 'wide'  && !document.getElementById('wide-table').tHead) renderWideTable();
}};

// --- Badge ---
function badge(status, text) {{
  var cls = status === 'ok' ? 'badge-ok' : (status === 'warn' ? 'badge-warn' : 'badge-err');
  return '<span class="' + cls + '">' + text + '</span>';
}}

// --- Snapshot checks ---
(function() {{
  var t = document.getElementById('snap-check-table');
  var h = '<thead><tr><th>Datum</th><th>Teams</th><th>Norm-Summe</th><th>Shin-Summe</th></tr></thead><tbody>';
  SNAP_CHECKS.forEach(function(c) {{
    h += '<tr>'
      + '<td>' + c.Datum + '</td>'
      + '<td>' + badge(c.teams_status, c.Teams) + '</td>'
      + '<td>' + badge(c.norm_status, c.norm_sum.toFixed(4) + '%') + '</td>'
      + '<td>' + badge(c.shin_status, c.shin_sum.toFixed(4) + '%') + '</td>'
      + '</tr>';
  }});
  t.innerHTML = h + '</tbody>';
}})();

// --- Global checks ---
(function() {{
  var t = document.getElementById('global-check-table');
  var h = '<thead><tr><th>Check</th><th>Ergebnis</th></tr></thead><tbody>';
  GLOBAL_CHECKS.forEach(function(c) {{
    h += '<tr><td>' + c.check + '</td><td>' + badge(c.status, c.wert) + '</td></tr>';
  }});
  t.innerHTML = h + '</tbody>';
}})();

// --- Long-Format ---
function initLongTab() {{
  var sel = document.getElementById('long-datum-filter');
  DATUMS.forEach(function(d) {{
    var opt = document.createElement('option');
    opt.value = d; opt.text = d;
    sel.appendChild(opt);
  }});
  sel.value = DATUMS[DATUMS.length - 1];
  renderLongTable();
}}

window.renderLongTable = function() {{
  var datum = document.getElementById('long-datum-filter').value;
  var rows  = LONG_DATA.filter(function(r) {{ return r.Datum === datum; }});
  rows.sort(function(a, b) {{ return b['Shin_%'] - a['Shin_%']; }});

  var h = '<thead><tr><th>Rang</th><th>Team</th><th>Datum</th><th>Ø Quote</th><th>Norm %</th><th>Shin %</th></tr></thead><tbody>';
  rows.forEach(function(r, i) {{
    h += '<tr>'
      + '<td style="color:#999">' + (i + 1) + '</td>'
      + '<td><b>' + r.Team + '</b></td>'
      + '<td>' + r.Datum + '</td>'
      + '<td>' + r.Quote.toFixed(2) + '</td>'
      + '<td>' + r['Norm_%'].toFixed(2) + '%</td>'
      + '<td style="color:#457B9D;font-weight:bold">' + r['Shin_%'].toFixed(2) + '%</td>'
      + '</tr>';
  }});
  document.getElementById('long-table').innerHTML = h + '</tbody>';
  document.getElementById('long-info').textContent = rows.length + ' Teams';
}};

// --- Wide-Format ---
function renderWideTable() {{
  var h = '<thead><tr>';
  WIDE_COLS.forEach(function(c) {{ h += '<th>' + c + '</th>'; }});
  h += '</tr></thead><tbody>';
  WIDE_ROWS.forEach(function(row) {{
    h += '<tr>';
    row.forEach(function(cell, j) {{
      var val = (cell === null || cell === 'nan') ? '–' : cell;
      if (j === 0) {{
        h += '<td style="font-weight:bold;position:sticky;left:0;background:white;z-index:1">' + val + '</td>';
      }} else {{
        var display = (typeof val === 'number') ? val.toFixed(2) : val;
        h += '<td>' + display + '</td>';
      }}
    }});
    h += '</tr>';
  }});
  document.getElementById('wide-table').innerHTML = h + '</tbody>';
}}

}})();
</script>
"""


# ---------------------------------------------------------------------------
# Analysen während der WM (Einzelspiel-Prognosen)
# ---------------------------------------------------------------------------

_DURING_WM_PLACEHOLDER = """
<div class="during-wm-section">
  <div class="inspection-title">&#128197; Analysen während der WM</div>
  <p class="during-wm-placeholder">Noch keine Daten – Scraper für Einzelspiele noch nicht ausgeführt.</p>
</div>
"""


def build_during_wm_section(df_during):
    """Erzeugt den HTML-Block mit Einzelspiel-1X2-Prognosen (Deutschland-Spiele)."""

    if df_during is None or df_during.empty:
        return _DURING_WM_PLACEHOLDER

    cards = []
    for _, sub in df_during.groupby("Spiel_ID", sort=False):
        sub = sub.set_index("Ausgang").reindex(OUTCOMES)
        if sub["Wahrscheinlichkeit_Shin_in_Prozent"].isna().any():
            continue

        heimteam    = sub["Heimteam"].iloc[0]
        gastteam    = sub["Gastteam"].iloc[0]
        datum       = sub["Datum"].iloc[0]
        last_update = sub["Letzte_Aktualisierung"].iloc[0]

        labels = {
            "Heimsieg":       f"Heimsieg ({heimteam})",
            "Unentschieden":  "Unentschieden",
            "Heimniederlage": f"Heimniederlage ({gastteam})",
        }

        bar_rows   = []
        table_rows = []
        for outcome in OUTCOMES:
            row  = sub.loc[outcome]
            shin = float(row["Wahrscheinlichkeit_Shin_in_Prozent"])
            norm = float(row["Wahrscheinlichkeit_in_Prozent"])

            bar_rows.append(f"""
            <div class="bar-row" data-shin="{shin}" data-norm="{norm}">
              <div class="bar-label">{labels[outcome]}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{shin}%"></div></div>
              <div class="bar-value">{shin:.1f}%</div>
            </div>""")

            table_rows.append(f"""
            <tr>
              <td>{labels[outcome]}</td>
              <td>{row['Durchsch_Quote']:.2f}</td>
              <td>{int(row['Anzahl_Buchmacher'])}</td>
              <td>{norm:.2f}%</td>
              <td>{shin:.2f}%</td>
            </tr>""")

        cards.append(f"""
    <div class="match-card">
      <div class="match-title">{heimteam} vs. {gastteam} &mdash; {datum}</div>
      <div class="match-bars">{''.join(bar_rows)}
      </div>
      <table class="match-table">
        <thead><tr><th>Ausgang</th><th>&Oslash; Quote</th><th># BK</th><th>Norm %</th><th>Shin %</th></tr></thead>
        <tbody>{''.join(table_rows)}</tbody>
      </table>
      <div class="match-footer">Stand: {last_update}</div>
    </div>""")

    if not cards:
        return _DURING_WM_PLACEHOLDER

    return f"""
<div class="during-wm-section">
  <div class="inspection-title">&#128197; Analysen während der WM</div>
  <div class="during-wm-controls">
    <span class="control-label">Methode:</span>
    <button id="btn-during-shin" class="btn active" onclick="setDuringMethod('shin')">Shin-Modell</button>
    <button id="btn-during-norm" class="btn"        onclick="setDuringMethod('norm')">Basic Normalisation</button>
  </div>
  <div class="match-cards">{''.join(cards)}
  </div>
</div>

<script>
function setDuringMethod(m) {{
  document.querySelectorAll('.during-wm-section .bar-row').forEach(function(el) {{
    var val = parseFloat(el.getAttribute('data-' + m));
    el.querySelector('.bar-fill').style.width = val + '%';
    el.querySelector('.bar-value').textContent = val.toFixed(1) + '%';
  }});
  ['shin', 'norm'].forEach(function(mm) {{
    var el = document.getElementById('btn-during-' + mm);
    if (el) el.classList.toggle('active', mm === m);
  }});
}}
</script>
"""


# ---------------------------------------------------------------------------
# Plotly-Figure bauen
# ---------------------------------------------------------------------------

def build_figure(df, ranking):
    top15  = ranking[:15]
    rest15 = ranking[15:30]
    latest = df["Datum"].max()

    fig          = go.Figure()
    trace_groups = {}
    idx          = 0

    for group_name, teams in [("top15", top15), ("rest15", rest15)]:
        for method, col in [
            ("shin", "Wahrscheinlichkeit_Shin_in_Prozent"),
            ("norm", "Wahrscheinlichkeit_in_Prozent"),
        ]:
            key                = f"{group_name}_{method}"
            trace_groups[key]  = []

            for i, team in enumerate(teams):
                team_df  = df[df["Team"] == team].sort_values("Datum")
                if team_df.empty:
                    continue

                cur_prob = team_df[col].iloc[-1]
                rank     = ranking.index(team) + 1

                if "Anzahl_Buchmacher" in team_df.columns:
                    customdata = team_df["Anzahl_Buchmacher"].fillna("?").astype(str).tolist()
                    hover_bk   = "Buchmacher: %{customdata}<br>"
                else:
                    customdata = None
                    hover_bk   = ""

                visible = (group_name == "top15" and method == "shin")

                fig.add_trace(go.Scatter(
                    x          = team_df["Datum"],
                    y          = team_df[col].round(2),
                    mode       = "lines+markers",
                    name       = f"{rank}. {team}  ({cur_prob:.1f}%)",
                    line       = dict(color=COLORS[i % len(COLORS)], width=2.3),
                    marker     = dict(size=7, color=COLORS[i % len(COLORS)]),
                    visible    = visible,
                    customdata = customdata,
                    hovertemplate=(
                        f"<b>{team}</b><br>"
                        "%{x|%d.%m.%Y}<br>"
                        "Wahrsch.: <b>%{y:.2f}%</b><br>"
                        + hover_bk +
                        "<extra></extra>"
                    ),
                ))
                trace_groups[key].append(idx)
                idx += 1

    return fig, trace_groups, idx, top15, rest15, latest


# ---------------------------------------------------------------------------
# Zeiträume für den Vor-/Während-der-WM-Filter berechnen
# ---------------------------------------------------------------------------

def compute_period_ranges(df):
    """Datumsbereiche (x-Achse) für 'Vor der WM' und 'Während der WM'."""
    wm_start = pd.Timestamp(wm_paths.WM_START_DATE)
    pad      = pd.Timedelta(days=1)

    pre_dates    = df.loc[df["Datum"] < wm_start, "Datum"]
    during_dates = df.loc[df["Datum"] >= wm_start, "Datum"]

    if not pre_dates.empty:
        pre_range = [
            (pre_dates.min() - pad).strftime("%Y-%m-%d"),
            (pre_dates.max() + pad).strftime("%Y-%m-%d"),
        ]
    else:
        pre_range = [
            (wm_start - pd.Timedelta(days=8)).strftime("%Y-%m-%d"),
            wm_start.strftime("%Y-%m-%d"),
        ]

    if not during_dates.empty:
        during_range = [
            (during_dates.min() - pad).strftime("%Y-%m-%d"),
            (during_dates.max() + pad).strftime("%Y-%m-%d"),
        ]
    else:
        during_range = [
            wm_start.strftime("%Y-%m-%d"),
            (wm_start + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        ]

    return {"pre": pre_range, "during": during_range}


# ---------------------------------------------------------------------------
# HTML bauen
# ---------------------------------------------------------------------------

def build_html(fig, trace_groups, total, top15, rest15, latest, inspection_html, during_wm_html, period_ranges):
    latest_str = latest.strftime("%d.%m.%Y")

    fig.update_layout(
        title=dict(
            text=f"WM 2026 – Top 1–15 · Shin-Modell · Stand: {latest_str}",
            font=dict(size=15, family="Arial"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            title="Datum", tickformat="%d.%m.",
            gridcolor="#E8E8E8", showgrid=True, tickangle=-30,
        ),
        yaxis=dict(
            title="Wahrscheinlichkeit (%)", ticksuffix="%",
            gridcolor="#E8E8E8", showgrid=True,
        ),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="white",
        legend=dict(
            x=1.01, y=1.0, xanchor="left", yanchor="top",
            font=dict(size=10.5),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#DDDDDD", borderwidth=1,
            title=dict(text="Team (aktuell)", font=dict(size=10, color="#666")),
        ),
        margin=dict(l=70, r=230, t=75, b=70),
        hovermode="x unified",
        height=640,
        font=dict(family="Arial, sans-serif", size=12),
    )

    plot_fragment = fig.to_html(
        full_html=False, include_plotlyjs=True, div_id="plotDiv",
        config={"responsive": True, "displayModeBar": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )

    tg_json     = json.dumps(trace_groups)
    top15_json  = json.dumps(top15)
    rest_json   = json.dumps(rest15)
    period_json = json.dumps(period_ranges)

    js = f"""
var traceGroups = {tg_json};
var totalTraces = {total};
var currentGroup  = 'top15';
var currentMethod = 'shin';

var PERIOD_RANGES = {period_json};
var currentPeriod = 'gesamt';

var TITLES = {{
  'top15_shin':  'WM 2026 – Top 1–15 · Shin-Modell · Stand: {latest_str}',
  'top15_norm':  'WM 2026 – Top 1–15 · Basic Normalisation · Stand: {latest_str}',
  'rest15_shin': 'WM 2026 – Rang 16–30 · Shin-Modell · Stand: {latest_str}',
  'rest15_norm': 'WM 2026 – Rang 16–30 · Basic Normalisation · Stand: {latest_str}',
}};

function updateChart() {{
  var key     = currentGroup + '_' + currentMethod;
  var visible = new Array(totalTraces).fill(false);
  traceGroups[key].forEach(function(i) {{ visible[i] = true; }});
  Plotly.restyle('plotDiv', {{visible: visible}});
  Plotly.relayout('plotDiv', {{'title.text': TITLES[key]}});
  ['top15','rest15'].forEach(function(g) {{
    var el = document.getElementById('btn-grp-' + g);
    if (el) el.classList.toggle('active', g === currentGroup);
  }});
  ['shin','norm'].forEach(function(m) {{
    var el = document.getElementById('btn-met-' + m);
    if (el) el.classList.toggle('active', m === currentMethod);
  }});
}}
function setGroup(g)  {{ currentGroup  = g; updateChart(); }}
function setMethod(m) {{ currentMethod = m; updateChart(); }}

function setPeriod(p) {{
  currentPeriod = p;
  if (p === 'gesamt') {{
    Plotly.relayout('plotDiv', {{'xaxis.autorange': true}});
  }} else {{
    Plotly.relayout('plotDiv', {{'xaxis.range': PERIOD_RANGES[p], 'xaxis.autorange': false}});
  }}
  ['gesamt','pre','during'].forEach(function(p2) {{
    var el = document.getElementById('btn-period-' + p2);
    if (el) el.classList.toggle('active', p2 === currentPeriod);
  }});
}}
"""

    css = """
* { box-sizing: border-box; }
body {
  font-family: Arial, sans-serif;
  margin: 0; padding: 16px 20px;
  background: #F0F2F5;
}
.page-header { text-align: center; margin-bottom: 12px; }
.page-header h1 { font-size: 19px; color: #2C3E50; margin: 0 0 3px; }
.page-header .meta { font-size: 11.5px; color: #888; }
.controls {
  display: flex; gap: 20px; justify-content: center;
  margin-bottom: 10px; flex-wrap: wrap;
}
.control-group { display: flex; align-items: center; gap: 6px; }
.control-label { font-size: 12px; color: #555; font-weight: bold; }
.btn {
  padding: 6px 18px; border: 1.5px solid #BBBBBB;
  background: white; color: #555; cursor: pointer;
  border-radius: 20px; font-size: 12.5px; font-family: Arial, sans-serif;
  transition: all 0.15s ease;
}
.btn:hover { border-color: #457B9D; color: #457B9D; }
.btn.active { background: #457B9D; border-color: #457B9D; color: white; font-weight: bold; }
#plotDiv { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.07); }
.footer { text-align: center; margin-top: 8px; font-size: 11px; color: #AAAAAA; }

/* ---- Datenkontrolle ---- */
.inspection-section {
  margin-top: 20px; background: white;
  border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.07);
  padding: 18px 20px 16px;
}
.inspection-title {
  font-size: 14px; font-weight: bold; color: #2C3E50; margin: 0 0 12px;
}
.insp-tab-bar {
  display: flex; margin-bottom: 14px; border-bottom: 2px solid #E8E8E8;
}
.insp-tab-btn {
  padding: 7px 18px; border: none; background: none; cursor: pointer;
  font-size: 12.5px; color: #777; font-family: Arial, sans-serif;
  border-bottom: 2px solid transparent; margin-bottom: -2px;
}
.insp-tab-btn:hover { color: #457B9D; }
.insp-tab-btn.active { color: #457B9D; border-bottom-color: #457B9D; font-weight: bold; }
.insp-tab-content { display: none; }
.insp-tab-content.active { display: block; }
.check-section-title {
  font-size: 12px; font-weight: bold; color: #555; margin-bottom: 6px;
}
.check-table { border-collapse: collapse; font-size: 12px; }
.check-table thead th {
  background: #F7F8FA; text-align: left; padding: 6px 12px;
  color: #555; font-size: 11.5px; border-bottom: 1px solid #E8E8E8;
}
.check-table tbody td { padding: 5px 12px; border-bottom: 1px solid #F5F5F5; }
.badge-ok   { background:#E8F5E9; color:#2E7D32; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:bold; }
.badge-warn { background:#FFF8E1; color:#F57F17; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:bold; }
.badge-err  { background:#FFEBEE; color:#C62828; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:bold; }
.filter-row { display:flex; gap:10px; align-items:center; margin-bottom:10px; flex-wrap:wrap; }
.filter-label { font-size:12px; color:#555; font-weight:bold; }
.filter-select {
  padding:4px 10px; border:1px solid #DDD; border-radius:4px;
  font-size:12px; font-family:Arial,sans-serif; background:white; cursor:pointer;
}
.table-info { font-size:11px; color:#999; }
.data-table-wrap {
  overflow-x:auto; max-height:460px; overflow-y:auto;
  border:1px solid #EBEBEB; border-radius:4px;
}
.data-table { border-collapse:collapse; font-size:12px; white-space:nowrap; }
.data-table thead th {
  position:sticky; top:0; z-index:2;
  background:#457B9D; color:white;
  padding:7px 12px; text-align:left; font-weight:600; font-size:11.5px;
}
.data-table tbody td { padding:5px 12px; border-bottom:1px solid #F5F5F5; }
.data-table tbody tr:hover td { background:#EEF6FF !important; }
.data-table tbody tr:nth-child(even) td { background:#FAFAFA; }

/* ---- Während der WM ---- */
.during-wm-section {
  margin-top: 20px; background: white;
  border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.07);
  padding: 18px 20px 16px;
}
.during-wm-placeholder { font-size: 12.5px; color: #999; margin: 0; }
.during-wm-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.match-cards { display: flex; flex-wrap: wrap; gap: 16px; }
.match-card {
  flex: 1 1 320px; min-width: 300px;
  border: 1px solid #EBEBEB; border-radius: 6px;
  padding: 14px 16px;
}
.match-title { font-size: 13px; font-weight: bold; color: #2C3E50; margin-bottom: 10px; }
.match-bars { margin-bottom: 12px; }
.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.bar-label { flex: 0 0 170px; font-size: 11.5px; color: #555; }
.bar-track {
  flex: 1; height: 14px; background: #F0F2F5;
  border-radius: 7px; overflow: hidden;
}
.bar-fill { height: 100%; background: #457B9D; border-radius: 7px; transition: width 0.2s ease; }
.bar-value { flex: 0 0 50px; text-align: right; font-size: 11.5px; font-weight: bold; color: #457B9D; }
.match-table { width: 100%; border-collapse: collapse; font-size: 11.5px; margin-bottom: 8px; }
.match-table thead th {
  background: #F7F8FA; text-align: left; padding: 5px 8px;
  color: #555; font-size: 11px; border-bottom: 1px solid #E8E8E8;
}
.match-table tbody td { padding: 4px 8px; border-bottom: 1px solid #F5F5F5; }
.match-footer { font-size: 10.5px; color: #AAAAAA; text-align: right; }
"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WM 2026 – Siegwahrscheinlichkeiten</title>
  <style>{css}</style>
</head>
<body>

<div class="page-header">
  <h1>WM 2026 – Zeitverlauf der Siegwahrscheinlichkeiten</h1>
  <div class="meta">
    Stand: {latest_str} &nbsp;&bull;&nbsp;
    Quellen: Oddschecker · Oddspedia · Wettfreunde &nbsp;&bull;&nbsp;
    Buchmacher: Unibet, Ladbrokes, Betway, Betfair, bet365, Bwin, Interwetten
  </div>
</div>

<div class="controls">
  <div class="control-group">
    <span class="control-label">Gruppe:</span>
    <button id="btn-grp-top15"  class="btn active" onclick="setGroup('top15')">Top 1 – 15</button>
    <button id="btn-grp-rest15" class="btn"        onclick="setGroup('rest15')">Rang 16 – 30</button>
  </div>
  <div class="control-group">
    <span class="control-label">Methode:</span>
    <button id="btn-met-shin" class="btn active" onclick="setMethod('shin')">Shin-Modell</button>
    <button id="btn-met-norm" class="btn"        onclick="setMethod('norm')">Basic Normalisation</button>
  </div>
  <div class="control-group">
    <span class="control-label">Zeitraum:</span>
    <button id="btn-period-gesamt" class="btn active" onclick="setPeriod('gesamt')">Gesamt</button>
    <button id="btn-period-pre"    class="btn"        onclick="setPeriod('pre')">Vor der WM</button>
    <button id="btn-period-during" class="btn"        onclick="setPeriod('during')">Während der WM</button>
  </div>
</div>

{plot_fragment}

<div class="footer">
  Institut für Sportinformatik &nbsp;&bull;&nbsp;
  Rang basiert auf aktuellster Shin-Wahrscheinlichkeit ({latest_str})
</div>

{inspection_html}

{during_wm_html}

<script>{js}</script>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Lade Daten...")
    df      = load_data()
    df_wide = load_wide(df)
    ranking = rank_teams(df)

    print(f"  {df['Datum'].nunique()} Snapshots | {df['Team'].nunique()} Teams")
    print(f"  Stand: {df['Datum'].max().strftime('%d.%m.%Y')}")

    print("Führe Datenkontrolle durch...")
    inspection_html = build_inspection_section(df, df_wide)

    print("Lade Einzelspiel-Prognosen (während der WM)...")
    df_during = load_during_wm_data()
    if df_during is not None:
        print(f"  {df_during['Spiel_ID'].nunique()} Spiel(e) gefunden")
    else:
        print("  Noch keine Daten (processed_data_during_wm/ fehlt).")
    during_wm_html = build_during_wm_section(df_during)

    print("Baue Visualisierung...")
    fig, trace_groups, total, top15, rest15, latest = build_figure(df, ranking)
    period_ranges = compute_period_ranges(df)

    print("Erzeuge HTML...")
    html = build_html(fig, trace_groups, total, top15, rest15, latest, inspection_html, during_wm_html, period_ranges)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nGespeichert: {OUTPUT_FILE}")
    print(f"  {total} Traces | {df['Datum'].nunique()} Snapshots | {df['Team'].nunique()} Teams")
    print(f"\nIm Browser öffnen: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
