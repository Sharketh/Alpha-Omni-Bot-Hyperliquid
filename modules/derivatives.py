import numpy as np
from scipy.stats import linregress

def get_slope(series):
    """Menghitung kemiringan tren menggunakan regresi linier."""
    try:
        # Tambahkan pengecekan jika data terlalu sedikit untuk regresi
        if len(series) < 5: return 0
        return linregress(np.arange(len(series)), np.array(series))[0]
    except:
        return 0

def analyze_derivatives(df, ticker, side):
    """
    Menganalisis metrik derivatif (Funding, Basis, CVD Divergence).
    """
    score = 1
    reasons = []
    
    # 1. Funding Rate Check
    # Pastikan mengambil funding rate yang benar dari info exchange
    funding = float(ticker.get('info', {}).get('fundingRate', 0))
    
    # Filter Keras: Jangan paksa entri jika funding melawan arah dengan ekstrim
    if side == "Long" and funding > 0.0002: # 0.02% 
        return False, 0, ["Funding Hot (>0.02%)"]
    
    if side == "Short" and funding < -0.0002:
        return False, 0, ["Funding Cold (<-0.02%)"]
    
    if abs(funding) < 0.0001: 
        score += 1
        reasons.append("Stable Funding")

    # 2. CVD Calculation (Self-Healing)
    # Menghitung Delta jika kolom CVD belum ada di dataframe
    if 'CVD' not in df.columns:
        df['delta'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
        df['CVD'] = df['delta'].cumsum()

    # 3. Divergence Analysis (Price vs CVD) - Window: 10 candle terakhir
    p_slope = get_slope(df['close'].iloc[-10:])
    cvd_slope = get_slope(df['CVD'].iloc[-10:])
    
    # Bearish Divergence: Harga naik tapi CVD turun (Distribusi/Absorpsi Seller)
    if p_slope > 0 and cvd_slope < 0:
        if side == "Short":
            score += 3 # Berikan bobot lebih tinggi untuk konfirmasi
            reasons.append("Bear CVD Div")
        elif side == "Long":
            score -= 2 

    # Bullish Divergence: Harga turun tapi CVD naik (Akumulasi/Absorpsi Buyer)
    elif p_slope < 0 and cvd_slope > 0:
        if side == "Long":
            score += 3
            reasons.append("Bull CVD Div")
        elif side == "Short":
            score -= 2

    return True, score, reasons
