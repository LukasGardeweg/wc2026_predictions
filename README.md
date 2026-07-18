# ⚽ World Cup 2026 – Win Probabilities Over Time

This project tracks the **win probabilities of all 48 teams** at the 2026 FIFA World Cup – from the first bookmaker odds before the tournament all the way through the live tournament. The underlying data are aggregated odds from major bookmakers, converted into probabilities using *Basic Normalisation* and the *Shin model*.

A project by the **Institute of Training Science and Sports Informatics** at the German Sport University Cologne (Lukas Gardeweg, Fabian Wunderlich, Daniel Memmert).

---

## 🎲 Randomness in football – why a 100% accurate prediction is impossible

Before diving into numbers, odds, and rankings, it's worth looking at a key finding from sports science that underpins this whole project:

> Wunderlich, Seck & Memmert (2021): *"The influence of randomness on goals in football decreases over time. An empirical analysis of randomness involved in goal scoring in the English Premier League."* Journal of Sports Sciences. https://doi.org/10.1080/02640414.2021.1930685

This study analysed **over 7,000 goals from seven seasons of the English Premier League**. The result: **almost every second goal (~50%)** shows a substantial element of randomness – deflections, post hits, own goals, or lucky/unlucky moments at decisive points in the game. This share of randomness is **even more pronounced for weaker teams** and additionally depends on the match situation (e.g. current scoreline, set pieces).

**What does this mean for this project?**

The win probabilities shown here are based on the odds of the largest bookmakers – essentially the collective assessment of millions of bettors combined with highly sophisticated prediction models. As such, they are among the best available estimates of each team's true chances of winning.

But: **a probability is not a promise.** Even a team with an 80% chance of winning statistically loses one out of every five times – and a single deflection, post hit, or penalty decision can turn any match around. This unavoidable element of chance is exactly what makes football so exciting. Upsets at this World Cup are therefore not proof that these predictions are "wrong" – they are a statistically completely normal part of the game.

---

### Time series of the Top 15

<video src="visualization_png/wm2026_zeitverlauf_top15_animation.mp4" controls></video>

An interactive version with additional filters (Top 15 / ranks 16–30, Shin vs. normalisation method, before/during the tournament) is available in [`wm2026_probabilities.html`](wm2026_probabilities.html) – just open it locally in a browser.

---

## ⚙️ How the predictions are made

1. **Scrape odds** – bookmaker odds are collected from Oddschecker, Oddspedia, and Wettfreunde and merged across seven target bookmakers (bet365, Bwin, Interwetten, Unibet, Ladbrokes, Betway, Betfair).
2. **Average the odds** – for each team, the mean odds across all available bookmakers are computed.
3. **Convert to probabilities** – the average odds are converted into probabilities in two ways:
   - **Basic Normalisation**: simply rescales the implied odds-based probabilities to sum to 100%.
   - **Shin model**: additionally corrects for the bookmakers' margin (overround) and provides a more accurate estimate of the "true" probabilities – this is the method used in the README charts.
4. **Store the time series** – each run creates a new snapshot (date + probabilities per team) that is appended to the existing time series.

---

## 🔄 Automatic Updates

To make sure the two charts above always show the **latest state**, a single command is enough:

```bash
python run_all.py
```

This command runs the complete pipeline:

1. Scrape odds from Wettfreunde, Oddspedia, and Oddschecker
2. Append the new data to `processed_data_long.xlsx`
3. **Regenerate the bar chart and time series in `visualization_png/`**

Before the tournament starts (11 June 2026), data is stored in `processed_data_pre_wm/`; afterwards it automatically switches to `processed_data_during_wm/`. The charts combine both periods into one continuous time series – so the prediction flows seamlessly from the pre-tournament phase into the live tournament.

If you only want to regenerate the charts (e.g. after manually adding new data), you can do that on its own:

```bash
python visualization_png/create_png_charts.py
```

---

## 📁 Project Structure

```
run_all.py                     Complete update pipeline (steps 1-5)
scraper_wettfreunde.py          Scraper: Wettfreunde / Interwetten
scraper_oddspedia.py            Scraper: Oddspedia (bet365, Bwin)
scraper_oddschecker.py          Scraper: Oddschecker (Unibet, Ladbrokes, Betway, Betfair)
update_processed_data.py        Odds -> probabilities (Basic Normalisation, Shin)
create_visualization.py         Interactive HTML visualization (wm2026_probabilities.html)
visualization_png/
  create_png_charts.py           Generates the README charts (bar chart & time series)
  wm2026_balkendiagramm_alle_teams.png
  wm2026_zeitverlauf_top15.png
processed_data_pre_wm/          Processed time series before the tournament
processed_data_during_wm/       Processed time series during the tournament
raw_data_pre_wm/ , raw_data_during_wm/   Raw scraper data
single_games_predictions/       Single-match predictions during the tournament
```

---

## 📚 Sources

- Wunderlich, F., Seck, A., & Memmert, D. (2021). *The influence of randomness on goals in football decreases over time. An empirical analysis of randomness involved in goal scoring in the English Premier League.* Journal of Sports Sciences. https://doi.org/10.1080/02640414.2021.1930685
- Odds: Oddschecker, Oddspedia, Wettfreunde (bookmakers: bet365, Bwin, Interwetten, Unibet, Ladbrokes, Betway, Betfair)
- Shin model for removing the bookmakers' margin (overround) from implied probabilities

---

## License

This project is licensed under the [MIT License](LICENSE).
