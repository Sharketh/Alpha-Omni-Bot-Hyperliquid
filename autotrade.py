import ccxt
import time
import os
import schedule
import logging
import threading
from datetime import datetime
from modules.config_loader import CONFIG
from modules.database import get_conn, release_conn

# --- ⚙️ CONFIGURATION ---
TARGET_LEVERAGE = 10    
RISK_PERCENT = 0.01           # Risk 1% of Equity per trade
MAX_POSITIONS = 20            # Max Concurrent OPEN positions
TP_SPLIT = [0.30, 0.30, 0.40] # 30% TP1, 30% TP2, 40% TP3

# Logging Setup
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HyperTrader")

# --- ⚙️ HYPERLIQUID CONFIG ---
exchange = ccxt.hyperliquid({
    'apiKey': os.getenv('HL_ACCOUNT_ADDRESS'), # Public Address
    'secret': os.getenv('HL_PRIVATE_KEY'),    # Private Key
    'options': {
        'defaultType': 'swap',
        'createMarketBuyOrderRequiresPrice': False
    }
})

# ---------------------------------------------------------
# 🛠️ DATABASE INITIALIZATION
# ---------------------------------------------------------
def init_execution_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS active_trades (
                id SERIAL PRIMARY KEY,
                signal_id INT,
                symbol VARCHAR(20),
                side VARCHAR(10),
                entry_price DECIMAL,
                sl_price DECIMAL,
                tp1 DECIMAL,
                tp2 DECIMAL,
                tp3 DECIMAL,
                quantity DECIMAL,
                leverage INT,
                order_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'PENDING',
                pnl DECIMAL DEFAULT 0,
                is_sl_moved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # ... (Table daily_reports tetap sama seperti kode Anda)
        conn.commit()
        logger.info("✅ Hyperliquid Execution DB Ready.")
    finally:
        release_conn(conn)

# ---------------------------------------------------------
# ⚡ TRADE LOGIC
# ---------------------------------------------------------
def place_split_tps(symbol, side, total_qty, tp1, tp2, tp3):
    try:
        # Determine Close Side
        tp_side = 'sell' if side.lower() in ['buy', 'long'] else 'buy'
        
        # Calculate precision-safe quantities
        q1 = float(exchange.amount_to_precision(symbol, total_qty * TP_SPLIT[0]))
        q2 = float(exchange.amount_to_precision(symbol, total_qty * TP_SPLIT[1]))
        q3 = float(exchange.amount_to_precision(symbol, total_qty * TP_SPLIT[2]))

        params = {'reduceOnly': True}
        
        logger.info(f"⚡ Placing TPs for {symbol}: {q1} | {q2} | {q3}")
        
        # Hyperliquid Limit Orders
        exchange.create_order(symbol, 'limit', tp_side, q1, float(tp1), params)
        exchange.create_order(symbol, 'limit', tp_side, q2, float(tp2), params)
        exchange.create_order(symbol, 'limit', tp_side, q3, float(tp3), params)
        
        return True
    except Exception as e:
        logger.error(f"⚠️ TP Placement Failed {symbol}: {e}")
        return False

# ---------------------------------------------------------
# 📥 SIGNAL INGESTION
# ---------------------------------------------------------
def ingest_fresh_signals():
    conn = get_conn()
    try:
        cur = conn.cursor()
        
        # Check Max Positions
        cur.execute("SELECT COUNT(*) FROM active_trades WHERE status IN ('OPEN', 'OPEN_TPS_SET')")
        current_active = cur.fetchone()[0]
        if current_active >= MAX_POSITIONS: return

        # Fetch Balance (Hyperliquid uses USDC)
        balance = exchange.fetch_balance()
        total_equity = float(balance['total']['USDC'])
        markets = exchange.load_markets()

        query = """
            SELECT t.id, t.symbol, t.side, t.entry_price, t.sl_price, t.tp1, t.tp2, t.tp3
            FROM trades t
            LEFT JOIN active_trades a ON t.id = a.signal_id
            WHERE t.status = 'Waiting Entry' AND a.id IS NULL
        """
        cur.execute(query)
        signals = cur.fetchall()
        
        for sig in signals:
            if current_active >= MAX_POSITIONS: break
            
            sig_id, sym, side, entry, sl, tp1, tp2, tp3 = sig
            entry = float(entry)
            
            # Risk Calc
            margin_allocated = total_equity * RISK_PERCENT
            position_value = margin_allocated * TARGET_LEVERAGE
            qty_coins = position_value / entry
            
            # Precision Fix
            qty_coins = float(exchange.amount_to_precision(sym, qty_coins))

            cur.execute("""
                INSERT INTO active_trades (signal_id, symbol, side, entry_price, sl_price, tp1, tp2, tp3, quantity, leverage, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
            """, (sig_id, sym, side, entry, sl, tp1, tp2, tp3, qty_coins, TARGET_LEVERAGE))
            
            logger.info(f"📥 Signal Ingested: {sym} | Value: ${position_value:.2f}")
            current_active += 1
            
        conn.commit()
    except Exception as e:
        logger.error(f"Ingest Error: {e}")
    finally:
        release_conn(conn)

# ---------------------------------------------------------
# 🚀 EXECUTION ENGINE
# ---------------------------------------------------------
def execute_pending_orders():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, symbol, side, entry_price, sl_price, quantity, leverage FROM active_trades WHERE status = 'PENDING'")
        orders = cur.fetchall()

        for order in orders:
            oid, sym, side, entry, sl, qty, lev = order
            try:
                # 1. Set Leverage
                try: exchange.set_leverage(int(lev), sym)
                except: pass

                # 2. Price Check
                ticker = exchange.fetch_ticker(sym)
                curr_price = float(ticker['last'])
                
                is_better = (side.lower() == 'long' and curr_price <= float(entry)) or \
                            (side.lower() == 'short' and curr_price >= float(entry))

                type_side = 'buy' if side.lower() == 'long' else 'sell'
                
                # Execute
                if is_better:
                    res = exchange.create_order(sym, 'market', type_side, qty)
                else:
                    res = exchange.create_order(sym, 'limit', type_side, qty, float(entry))
                
                if res:
                    cur.execute("UPDATE active_trades SET order_id = %s, status = 'OPEN' WHERE id = %s", (res['id'], oid))
                    conn.commit()
                    logger.info(f"✅ Order Placed: {sym}")

            except Exception as e:
                logger.error(f"❌ Exec Failed {sym}: {e}")
    finally:
        release_conn(conn)

# ---------------------------------------------------------
# 🛡️ SAFETY NET (Hyperliquid Polling)
# ---------------------------------------------------------
def monitor_active_trades():
    """Backup untuk mendeteksi Fill dan PnL tanpa WebSocket berat."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, symbol, side, entry_price, tp1, quantity FROM active_trades WHERE status = 'OPEN'")
        open_trades = cur.fetchall()

        for t in open_trades:
            tid, sym, side, entry, tp1, qty = t
            pos = exchange.fetch_position(sym)
            
            # Jika posisi sudah terisi (Size > 0)
            if float(pos['contracts']) > 0:
                success = place_split_tps(sym, side, float(pos['contracts']), tp1, t[5], t[6]) # tp1, tp2, tp3
                if success:
                    cur.execute("UPDATE active_trades SET status = 'OPEN_TPS_SET' WHERE id = %s", (tid,))
                    conn.commit()

    finally:
        release_conn(conn)

# ---------------------------------------------------------
# 🏁 MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    init_execution_db()
    
    # Scheduler
    schedule.every(1).minutes.do(ingest_fresh_signals)
    schedule.every(10).seconds.do(execute_pending_orders)
    schedule.every(30).seconds.do(monitor_active_trades) # Polling sebagai ganti WS Bybit
    
    logger.info("🚀 Hyperliquid Bot is LIVE.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)
