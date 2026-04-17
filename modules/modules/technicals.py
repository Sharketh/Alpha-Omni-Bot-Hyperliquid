import pandas_ta as ta
import numpy as np
from scipy.signal import argrelextrema

def detect_divergence(df):
    """
    Mendeteksi Bullish dan Bearish Divergence antara Harga dan StochRSI (K).
    Divergence sering kali menjadi sinyal awal pembalikan tren.
    """
    score = 0
    reasons = []
    close = df['close'].values
    # Pastikan stoch_rsi_k sudah dihitung sebelum memanggil fungsi ini
    if 'stoch_rsi_k' not in df.columns:
        return 0, ""
        
    k = df['stoch_rsi_k'].values
    
    # Mencari titik puncak (high) dan lembah (low) lokal
    high_idx = argrelextrema(close, np.greater, order=3)[0]
    low_idx = argrelextrema(close, np.less, order=3)[0]

    # 1. Deteksi Bearish Divergence (Harga buat Higher High, Indikator buat Lower High)
    if len(high_idx) >= 2:
        if close[high_idx[-1]] > close[high_idx[-2]] and k[high_idx[-1]] < k[high_idx[-2]]:
            score -= 2
            reasons.append("Bear Div")
    
    # 2. Deteksi Bullish Divergence (Harga buat Lower Low, Indikator buat Higher Low)
    if len(low_idx) >= 2:
        if close[low_idx[-1]] < close[low_idx[-2]] and k[low_idx[-1]] > k[low_idx[-2]]:
            score += 2
            reasons.append("Bull Div")
            
    return score, ", ".join(reasons)

def get_technicals(df):
    """
    Menghitung indikator utama yang digunakan untuk scoring dan charting.
    """
    # 1. Moving Averages (Trend Filter)
    df['EMA_Fast'] = ta.ema(df['close'], length=13)
    df['EMA_Slow'] = ta.ema(df['close'], length=21)
    
    # 2. Stochastic RSI (Momentum)
    stoch = ta.stochrsi(df['close'], length=14, k=3, d=3)
    if stoch is not None:
        # pandas_ta mengembalikan DataFrame, kita ambil kolom K dan D
        df['stoch_rsi_k'] = stoch[stoch.columns[0]]
        df['stoch_rsi_d'] = stoch[stoch.columns[1]]
    
    # 3. MACD (Trend & Momentum)
    macd = ta.macd(df['close'])
    if macd is not None:
        # Kolom kedua biasanya adalah Histogram (MACD_h)
        df['MACD_h'] = macd[macd.columns[1]]
        
    # Membersihkan data dari nilai NaN akibat perhitungan window (moving average)
    df.dropna(inplace=True)
    return df
