import ccxt
import time
import schedule
import random
import os
import pandas as pd
import pandas_ta as ta
import numpy as np
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Module Imports
from modules.config_loader import CONFIG
from modules.database import init_db, get_active_signals
from modules.technicals import get_technicals, detect_divergence
from modules.quant import calculate_metrics, check_fakeout
from modules.derivatives import analyze_derivatives
from modules.smc import analyze_smc
from modules.patterns import find_pattern
from modules.discord_bot import send_alert, update_status_dashboard, run_fast_update, send_scan_completion

# --- HYPERLIQUID INITIALIZATION ---
# Hyperliquid di CCXT memerlukan konfigurasi khusus untuk private key
exchange = ccxt.hyperliquid({
    'apiKey': os.getenv('HL_ACCOUNT_ADDRESS'), # Wallet Address
    'secret': os.getenv('HL_PRIVATE_KEY'),    # Private Key
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap' # Hyperliquid fokus pada Perpetual Swap
    }
})

def get_btc_bias():
    try:
        # Hyperliquid menggunakan simbol seperti 'BTC/USDC:USDC' atau 'BTC'
        bars = exchange.fetch_ohlcv('BTC/USDC', '1d', limit=100)
        if not bars: return "Sideways"
        df = pd.DataFrame(bars, columns=['t','o','h','l','c','v'])
        df['ema13'] = ta.ema(df['c'], length=13)
        df['ema21'] = ta.ema(df['c'], length=21)
        curr = df.iloc[-1]
        return "Bullish" if curr['ema13'] > curr['ema21'] else "Bearish"
    except Exception as e:
        print(f"Error BTC Bias: {e}")
        return "Sideways"

def calculate_rr(entry, sl, tp3):
    if entry <= 0 or sl <= 0 or tp3 <= 0: return 0.0
    risk = abs(entry - sl)
    if risk == 0: return 0.0
    return round(abs(tp3 - entry) / risk, 2)

def analyze_ticker(symbol, timeframe, btc_bias, active_signals):
    # 1. DUPLICATE CHECK
    if (symbol, timeframe) in active_signals: return None
    
    try:
        ticker_info = exchange.fetch_ticker(symbol)
        
        # Hyperliquid specific: Periksa apakah koin sedang dalam mode 'tradeable'
        if not ticker_info.get('info'): return None
        
        min_candles = CONFIG['system'].get('min_candles_analysis', 150)
        bars = exchange.fetch_ohlcv(symbol, timeframe, limit=min_candles + 50)
        
        if not bars or len(bars) < min_candles: return None
            
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 2. Technicals & Pattern
        df = get_technicals(df)
        pattern = find_pattern(df)
        if not pattern: return None
        side = CONFIG['pattern_signals'].get(pattern)
        
        # 3. SMC Analysis (Alpha-Omni Core)
        valid_smc, smc_score, smc_reasons = analyze_smc(df, side)
        min_smc = CONFIG['strategy'].get('min_smc_score', 0)
        if smc_score < min_smc: return None

        # 4. Quant & Deriv Metrics
        # Catatan: Hyperliquid menyediakan data OBI dan Funding yang sangat akurat
        df, basis, z_score, zeta_score, obi, quant_score, quant_reasons = calculate_metrics(df, ticker_info)
        valid_deriv, deriv_score, deriv_reasons = analyze_derivatives(df, ticker_info, side)
        
        if not valid_deriv or deriv_score < CONFIG['strategy'].get('min_deriv_score', 0):
            return None
        
        # 5. Scores & Bias Filtering
        div_score, div_msg = detect_divergence(df)
        tech_score = 3 + div_score
        
        if tech_score < CONFIG['strategy']['min_tech_score']: return None
        
        # Trend Alignment
        if "Bearish" in btc_bias and side == "Long": return None
        if "Bullish" in btc_bias and side == "Short": return None
        
        # Fakeout Protection
        valid_fo, fo_msg = check_fakeout(df, CONFIG['indicators']['min_rvol'])
        if not valid_fo: return None

        # 6. Fibonacci Setup (SMC Style)
        s = CONFIG['setup']
        lookback = 50
        swing_high = df['high'].iloc[-lookback:].max()
        swing_low = df['low'].iloc[-lookback:].min()
        rng = swing_high - swing_low
        
        if side == 'Long':
            entry = (swing_high - (rng * s['fib_entry_start']) + swing_high - (rng * s['fib_entry_end'])) / 2
            sl = swing_low - (rng * s['fib_sl'])
            tp1, tp2, tp3 = swing_low + rng, swing_low + (rng*1.618), swing_low + (rng*2.618)
        else:
            entry = (swing_low + (rng * s['fib_entry_start']) + swing_low + (rng * s['fib_entry_end'])) / 2
            sl = swing_high + (rng * s['fib_sl'])
            tp1, tp2, tp3 = swing_high - rng, swing_high - (rng*1.618), swing_high - (rng*2.618)
            
        rr = calculate_rr(entry, sl, tp3)
        if rr < CONFIG['strategy'].get('risk_reward_min', 2.0): return None
        
        # 7. Final Payload
        return {
            "Symbol": symbol, "Side": side, "Timeframe": timeframe, "Pattern": pattern,
            "Entry": float(entry), "SL": float(sl), "TP1": float(tp1), "TP2": float(tp2), "TP3": float(tp3), "RR": float(rr),
            "Tech_Score": int(tech_score), "Quant_Score": int(quant_score), 
            "Deriv_Score": int(deriv_score), "SMC_Score": int(smc_score),
            "Basis": float(basis), "Z_Score": float(z_score), "Zeta_Score": float(zeta_score), "OBI": float(obi),
            "BTC_Bias": btc_bias, "Reason": pattern, 
            "Tech_Reasons": ", ".join([pattern, div_msg]),
            "Quant_Reasons": ", ".join(quant_reasons),
            "SMC_Reasons": ", ".join([r for r in smc_reasons if r]),
            "Deriv_Reasons": ", ".join(deriv_reasons), 
            "df": df
        }
    except Exception:
        # traceback.print_exc() # Aktifkan jika ingin debug mendalam
        return None

def scan():
    start_time = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] 🔭 Hyperliquid Scanning... Mode: {os.getenv('BOT_ENV', 'PROD')}")
    
    btc_bias = get_btc_bias()
    print(f"📊 Market Bias: {btc_bias}")
    
    active_signals = get_active_signals()
    signal_count = 0 
    
    try:
        mkts = exchange.load_markets()
        
        # Hyperliquid Filter: Mencari koin yang aktif diperdagangkan di Perp L1
        syms = [
            s for s in mkts 
            if mkts[s].get('swap') 
            and mkts[s].get('active')
            and '/USDC' in s  # Hyperliquid menggunakan USDC sebagai quote utama
        ]
        
        random.shuffle(syms)
        print(f"🔍 Checking {len(syms)} Hyperliquid Pairs...")

        for tf in reversed(CONFIG['system']['timeframes']):
            print(f"  > Timeframe: {tf}")
            with ThreadPoolExecutor(max_workers=CONFIG['system']['max_threads']) as ex:
                futures = [ex.submit(analyze_ticker, s, tf, btc_bias, active_signals) for s in syms]
                for f in as_completed(futures):
                    res = f.result()
                    if res: 
                        success = send_alert(res)
                        if success: signal_count += 1
                        
    except Exception as e: 
        print(f"🛑 Critical Scan Error: {e}")
    finally:
        duration = time.time() - start_time
        print(f"✅ Scan Finished. Duration: {duration:.2f}s | Signals Found: {signal_count}")
        send_scan_completion(signal_count, duration, btc_bias)

if __name__ == "__main__":
    init_db()
    
    # Jalankan scan pertama kali
    scan()
    
    # Setup Penjadwalan
    interval = CONFIG['system'].get('check_interval_hours', 1)
    schedule.every(interval).hours.do(scan)
    schedule.every(1).minutes.do(run_fast_update)
    
    print(f"🚀 Alpha-Omni Hyperliquid Bot is running...")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("Terminating bot...")
            break
        except Exception as e:
            print(f"Runtime Error: {e}")
            time.sleep(10)
