import yfinance as yf
import sys
import time
import datetime

"""
Testing the Bursa Malaysia stock data analysis using yfinance and beautifulsoup4 libraries. The script will fetch stock data, perform analysis, and display results.
"""

def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    hist = stock.history(period="1y")
    info = stock.info

    if hist.empty:
        return None

    latest = hist.iloc[-1]

    return {
        "Stock Code": symbol,
        "Name": info.get("shortName", ""),
        "Sector": info.get("sector", ""),
        "Open": round(latest["Open"], 4),
        "High": round(latest["High"], 4),
        "Low": round(latest["Low"], 4),
        "Close": round(latest["Close"], 4),
        "Volume": int(latest["Volume"]),
        "P/E Ratio": info.get("trailingPE", ""),
        "ROE": info.get("returnOnEquity", ""),
        "EPS": info.get("trailingEps", ""),
        "P/B Ratio": info.get("priceToBook", ""),
        "SMA 20": round(hist["Close"].rolling(20).mean().iloc[-1], 4),
        "SMA 50": round(hist["Close"].rolling(50).mean().iloc[-1], 4),
        "SMA 200": round(hist["Close"].rolling(200).mean().iloc[-1], 4),
    }

result = get_stock_data("1155.KL")
print(result)

import pandas as pd

df = pd.DataFrame([result])
df.to_csv("/home/amar/Documents/VSCode Python/Bursa_Counter_Analysis/output.csv", index=False)