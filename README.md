# Bursa Screener

Stock screener applicable for Bursa Malaysia counters that automatically consolidates counters data. Built on top of `yfinance`, it pulls key financial metrics and exports everything into '.csv'

---

## Features

- **Complete Bursa coverage** — includes `bursa_tickers.py`, a curated list of all equity counters listed on Bursa Malaysia
- **Key metrics** — OHLC, SMA 20/50/200, ADR%, EPS, P/E ratio
- **Performance tracking** — 5D, 1M, 3M price performance
- **Shariah screening** — heuristic-based Shariah compliance check
- **Auto CSV export** — timestamped output sorted by market cap

---

## Usage

```bash
# Run full scan (all counters)
python Bursa_Analysis.py

# Limit to first N counters (for testing)
python Bursa_Analysis.py --limit 50

# Filter by keyword
python Bursa_Analysis.py --search GLOVE
```

---

## Requirements

```bash
pip install yfinance pandas rich
```

---

## Output

Generates a timestamped CSV file, e.g. `bursa_screener_20260601_1045.csv`, with the following columns:

`Code` · `Name` · `Sector` · `Open` · `High` · `Low` · `Close` · `SMA20` · `SMA50` · `SMA200` · `Shariah` · `ADR%` · `Perf 5D%` · `Perf 1M%` · `Perf 3M%` · `EPS` · `P/E` · `Volume` · `Mkt Cap`

---

## Disclaimer

1. I use this screener on top of fundamental and technical analysis (Volume-Price Analysis) to further scrutinize the counters list. What I do usually is copy the '.csv' file created by the program and paste it into my sheets that pre-set with conditional formatting and filters
2. Shariah compliancy tag are purely heuristic, recommended to manually scrutinize
3. There are few counters might be unavailable in yfinace and will be dropped from the .csv
