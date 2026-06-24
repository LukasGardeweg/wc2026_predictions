---
name: update-predictions
description: Run the full WC2026 prediction pipeline (scrape → process → visualize), then commit all output files with the standard "Update predictions DD.MM.YYYY" message.
disable-model-invocation: false
---

Run the full WC2026 predictions pipeline and commit the results.

## Steps

1. Run `python run_all.py --headless` from the project root. Wait for it to complete and report any errors or warnings (especially `[WARNUNG]` lines about unknown team names).

2. Stage the following output files for the commit:
   - `wm2026_probabilities.html`
   - `visualization_png/wm2026_balkendiagramm_alle_teams.png`
   - `visualization_png/wm2026_zeitverlauf_top15.png`
   - `processed_data_during_wm/processed_data_long.xlsx`
   - `processed_data_during_wm/processed_data_wide.xlsx`
   - `single_games_predictions/processed_match_predictions.xlsx`
   - `single_games_predictions/raw_single_odds_during_wm.xlsx`
   - Any new raw data files in `raw_data_during_wm/` (pattern: `wm2026_*.xlsx`)

3. Check `git status` to confirm which files changed. If nothing changed (no new odds data today), report that and stop — don't create an empty commit.

4. Commit using today's date in the format **DD.MM.YYYY** matching the existing commit style:
   ```
   Update predictions DD.MM.YYYY
   ```
   Example: `Update predictions 23.06.2026`

5. Report any `[WARNUNG]` messages from the scraper output — these indicate unknown team names that need to be added to `VALID_TEAMS` or `NAME_MAP`.

## Notes

- If the scraper fails due to Cloudflare blocks on Oddspedia, suggest running `python scraper_oddspedia.py` without `--headless` (visible browser mode) and then rerunning `python update_processed_data.py` + `python create_visualization.py` manually.
- Do not push — the user pushes manually.
