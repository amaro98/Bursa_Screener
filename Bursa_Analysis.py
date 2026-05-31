"""
Bursa Malaysia Stock Screener
Fetches OHLC, SMA, Shariah status, ADR, Performance, EPS, P/E
"""

import sys
import time
import argparse
import datetime
import pandas as pd
import yfinance as yf

from bursa_tickers import BURSA_TICKERS, search_bursa



def check_shariah(info):
    """
    Check Shariah compliance heuristic.
    Returns 'Y', 'N', or '' if unable to determine.
    Note: For official status, cross-reference with SC Malaysia's list.
    """
    # yfinance doesn't provide Shariah status directly.
    # We use a heuristic: check if the stock appears in Islamic ETFs
    # or if sector is clearly non-compliant.
    non_shariah_industries = [
        "gambling", "casino", "brewery", "distillery", "tobacco",
        "alcohol", "liquor", "wine", "beer", "betting",
    ]
    industry = (info.get("industry") or "").lower()
    sector = (info.get("sector") or "").lower()

    for keyword in non_shariah_industries:
        if keyword in industry or keyword in sector:
            return "N"
    return ""  # Can't confirm — leave blank


def compute_sma(hist, period):
    """Compute Simple Moving Average."""
    if hist is None or len(hist) < period:
        return None
    return round(hist["Close"].rolling(window=period).mean().iloc[-1], 4)


def compute_adr(hist, days=20):
    """Compute Average Daily Range (%) over last N days."""
    if hist is None or len(hist) < days:
        return None
    recent = hist.tail(days)
    daily_range = ((recent["High"] - recent["Low"]) / recent["Low"]) * 100
    return round(daily_range.mean(), 2)


def compute_performance(hist, days):
    """Compute price performance (%) over N days."""
    if hist is None or len(hist) < days:
        return None
    current = hist["Close"].iloc[-1]
    past = hist["Close"].iloc[-days]
    if past == 0:
        return None
    return round(((current - past) / past) * 100, 2)


def fetch_stock_data(code, name, retries=2):
    """Fetch all data for one ticker."""
    symbol = f"{code}.KL"

    for attempt in range(retries):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1y")

            if hist.empty:
                return None

            latest = hist.iloc[-1]
            info = stock.info or {}

            # OHLC
            o = round(latest.get("Open", 0), 4)
            h = round(latest.get("High", 0), 4)
            l = round(latest.get("Low", 0), 4)
            c = round(latest.get("Close", 0), 4)

            # SMAs
            sma20 = compute_sma(hist, 20)
            sma50 = compute_sma(hist, 50)
            sma200 = compute_sma(hist, 200)

            # Shariah
            shariah = check_shariah(info)

            # Price
            price = c

            # ADR
            adr = compute_adr(hist, 20)

            # Performance
            perf_5d = compute_performance(hist, 5)
            perf_1m = compute_performance(hist, 20)
            perf_3m = compute_performance(hist, 60)

            # EPS & P/E
            eps = info.get("trailingEps", "")
            pe = info.get("trailingPE", info.get("forwardPE", ""))

            return {
                "Code": code,
                "Name": info.get("shortName", name),
                "Sector": info.get("sector", ""),
                "Open": o,
                "High": h,
                "Low": l,
                "Close": c,
                "SMA20": sma20,
                "SMA50": sma50,
                "SMA200": sma200,
                "Shariah": shariah,
                "Price": price,
                "ADR%": adr,
                "Perf 5D%": perf_5d,
                "Perf 1M%": perf_1m,
                "Perf 3M%": perf_3m,
                "EPS": eps,
                "P/E": pe,
                "Volume": int(latest.get("Volume", 0)),
                "Mkt Cap": info.get("marketCap", ""),
            }

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f"  ✗ {code} {name} — {e}")
                return None
    return None


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Bursa Malaysia Stock Screener")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tickers (0=all)")
    parser.add_argument("--search", type=str, default="", help="Filter tickers by keyword")
    args = parser.parse_args()

    print("=" * 60)
    print("  BURSA MALAYSIA STOCK SCREENER")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Build ticker list
    if args.search:
        tickers = search_bursa(args.search)
        print(f"\n  Search: '{args.search}' → {len(tickers)} matches")
    else:
        tickers = BURSA_TICKERS

    if args.limit > 0:
        tickers = tickers[:args.limit]

    total = len(tickers)
    print(f"  Tickers to process: {total}\n")

    results = []
    failed = 0
    start_time = time.time()

    for i, (code, name) in enumerate(tickers, 1):
        pct = (i / total) * 100
        elapsed = time.time() - start_time
        eta = (elapsed / i) * (total - i) if i > 0 else 0
        eta_str = f"{int(eta//60)}m{int(eta%60)}s"

        sys.stdout.write(
            f"\r  [{i}/{total}] ({pct:.0f}%) {code} {name[:30]:<30} ETA: {eta_str}   "
        )
        sys.stdout.flush()

        data = fetch_stock_data(code, name)
        if data:
            results.append(data)
        else:
            failed += 1

        # Rate limit: pause every 5 tickers
        if i % 5 == 0:
            time.sleep(1)

    elapsed_total = time.time() - start_time
    print(f"\n\n  ✓ Fetched: {len(results)} / {total}  (failed: {failed})")
    print(f"  Time: {int(elapsed_total//60)}m {int(elapsed_total%60)}s")

    if not results:
        print("  No data fetched. Check your internet connection.")
        return

    # Build DataFrame
    df = pd.DataFrame(results)
    df["Mkt Cap"] = pd.to_numeric(df["Mkt Cap"], errors="coerce")
    df = df.sort_values("Mkt Cap", ascending=False, na_position="last")

    # Save
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"bursa_screener_{timestamp}.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"\n  ✓ Saved: {filename}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\n  Top 10 by Market Cap:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()