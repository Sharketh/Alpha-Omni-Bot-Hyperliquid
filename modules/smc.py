import pandas as pd

def detect_order_block(df):
    # Logika mendeteksi candle terakhir sebelum pergerakan impulsif
    # (High-probability zone untuk entry di Hyperliquid)
    last_candle = df.iloc[-1]
    # ... logic detection ...
    return is_ob_detected
