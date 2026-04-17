import numpy as np
import pandas_ta as ta
from scipy.special import expit

def calculate_z_score(series, window=20):
    """
    Menghitung seberapa jauh harga/volume menyimpang dari rata-rata (standar deviasi).
    """
    mean = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    return (series - mean) / std

def calculate_zeta_field(df, basis):
    """
    Kalkulasi Zeta Field: Menggabungkan Volatility, Flow, Momentum, dan Basis 
    menjadi satu skor probabilitas (0-100).
    """
    try:
        # 1. Volatility Term (NATR)
        natr = ta.natr(df['high'], df['low'], df['close'], length=14)
        v_term = expit(natr.iloc[-1])
        
        # 2. Flow Term (Chaikin Money Flow)
        cmf = ta.cmf(df['high'], df['low'], df['close'], df['volume'], length=20)
        f_term = (cmf.iloc[-1] + 1) / 2 # Normalize -1 to 1 into 0 to 1
        
        # 3. Cycle Term (CCI)
        cci = ta.cci(df['high'], df['low'], df['close'], length=20)
        c_term = expit(cci.iloc[-1] / 100)
        
        # 4. Basis Term (Gap Perp vs Index)
        b_term = 1.0 - min(abs(basis) * 100, 1.0)
        
        # 5. Sentiment Term (RSI)
        rsi = ta.rsi(df['close'], length=14)
        s_term = rsi.iloc[-1] / 100.0
        
        # 6. Acceleration Term (ROC)
        roc = ta.ta_roc = ta.roc(df['close'], length=9)
        a_term = expit(roc.iloc[-1])
        
        # 7. Hype/Volume Term (RVOL)
        rvol = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
        h_term = min(rvol / 5.0, 1.0)
        
        # 8. Trend Term (ADX)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        t_term = adx['ADX_14'].iloc[-1] / 100.0
        
        # Totaling Zeta Score
        zeta_raw = (v_term + f_term + c_term + b_term + s_term + a_term + h_term + t_term)
        zeta_score = (zeta_raw / 8.0) * 100.0
        
        score_add, reason = 0, ""
        if zeta_score > 70: 
            score_add, reason = 1, f"ζ-High ({zeta_score:.1f})"
        elif zeta_score < 30: 
            score_add, reason = 1, f"ζ-Low ({zeta_score:.1f})"
            
        return zeta_score, score_add, reason
    except: 
        return 50.0, 0, ""

def calculate_obi(ticker):
    """
    Order Book Imbalance: Mengukur dominasi buyer vs seller di bid/ask volume.
    """
    try:
        bid, ask = float(ticker.get('bidVolume', 0)), float(ticker.get('askVolume', 0))
        return (bid - ask) / (bid + ask) if (bid + ask) > 0 else 0.0
    except: 
        return 0.0

def calculate_metrics(df, ticker):
    """
    Main entry point untuk menghitung semua metrik kuantitatif.
    """
    mark = float(ticker.get('last', 0))
    index = float(ticker.get('info', {}).get('indexPrice', mark))
    basis = (mark - index) / index if index > 0 else 0
    
    # Volume Analysis
    df['Vol_SMA'] = ta.sma(df['volume'], length=20)
    df['RVOL'] = df['volume'] / df['Vol_SMA']
    df['Vol_Z'] = calculate_z_score(df['volume'], window=20)
    
    z_score = df['Vol_Z'].iloc[-1]
    zeta_score, zeta_bonus, zeta_reason = calculate_zeta_field(df, basis)
    obi = calculate_obi(ticker)
    
    # Scoring System
    score, reasons = 2, []
    
    # RVOL Scoring
    curr_rvol = df['RVOL'].iloc[-1]
    if curr_rvol > 5.0: 
        score += 1
        reasons.append("Nuclear RVOL")
    elif curr_rvol > 2.0: 
        reasons.append("Valid RVOL")
    
    # Z-Score Scoring (High volatility signal)
    if z_score > 3.0: 
        score += 2
        reasons.append(f"Z-Score ({z_score:.1f})")
        
    # Zeta & OBI Scoring
    if zeta_bonus > 0: 
        score += zeta_bonus
        reasons.append(zeta_reason)
        
    if abs(obi) > 0.3: 
        score += 1
        reasons.append(f"OBI {obi:.2f}")

    return df, basis, z_score, zeta_score, obi, score, reasons

def check_fakeout(df, min_rvol):
    """
    Memastikan breakout disertai volume yang cukup untuk menghindari fakeout.
    """
    if df['RVOL'].iloc[-1] < min_rvol: 
        return False, "Fakeout (Low Vol)"
    return True, ""
