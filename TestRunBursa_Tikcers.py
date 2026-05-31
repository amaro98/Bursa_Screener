from bursa_tickers import get_all_bursa_tickers, search_bursa

# Get all 1038 tickers in yfinance format
tickers = get_all_bursa_tickers()  # ["5250.KL", "7167.KL", ...]

# Search by name
x = search_bursa("PETRONAS")   # [("1155", "MALAYAN BANKING BERHAD")]
y = search_bursa("GLOVE")     # returns all glove companies

prin(x)