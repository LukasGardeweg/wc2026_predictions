---
name: commit-predictions
description: Stage the standard WC2026 prediction output files and commit with the "Update predictions DD.MM.YYYY" message — without re-running the pipeline.
disable-model-invocation: false
---

Stage prediction output files and create a standardized commit. Use this when the pipeline has already been run and you just need to commit the results.

## Steps

1. Run `git status` to see what changed.

2. Stage only the standard prediction output files:
   - `wm2026_probabilities.html`
   - `visualization_png/wm2026_balkendiagramm_alle_teams.png`
   - `visualization_png/wm2026_zeitverlauf_top15.png`
   - `processed_data_during_wm/processed_data_long.xlsx`
   - `processed_data_during_wm/processed_data_wide.xlsx`
   - `single_games_predictions/processed_match_predictions.xlsx`
   - `single_games_predictions/raw_single_odds_during_wm.xlsx`
   - Any new raw data files in `raw_data_during_wm/` (pattern: `wm2026_*.xlsx`)

   Do not add unrelated Python script changes unless the user explicitly says to include them.

3. If nothing changed, report that and stop — don't create an empty commit.

4. Commit using today's date in the **DD.MM.YYYY** format:
   ```
   Update predictions DD.MM.YYYY
   ```
   Example: `Update predictions 23.06.2026`

5. Show the commit hash and summary so the user can verify before pushing.

## Notes

- Do not push — the user pushes manually.
- If the user has made Python script changes they also want to include, ask before staging them.
