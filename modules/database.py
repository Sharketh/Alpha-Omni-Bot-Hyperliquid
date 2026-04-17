import psycopg2
from psycopg2 import pool
import logging
from modules.config_loader import CONFIG

# Logging Setup
logger = logging.getLogger("Database")

DB_POOL = None

def init_db():
    global DB_POOL
    try:
        # Mengambil dari config atau default ke 20 jika tidak ada
        pool_size = CONFIG.get('system', {}).get('max_threads', 15) + 5
        
        DB_POOL = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, 
            maxconn=pool_size,
            host=CONFIG['database']['host'], 
            database=CONFIG['database']['database'],
            user=CONFIG['database']['user'], 
            password=CONFIG['database']['password'],
            port=CONFIG['database']['port']
        )
        
        conn = DB_POOL.getconn()
        try:
            migrate_schema(conn)
        finally:
            DB_POOL.putconn(conn)
            
        logger.info("✅ Database Connected & Schema Synced.")
        
    except Exception as e:
        logger.error(f"❌ DB Init Error: {e}")
        exit(1)

def migrate_schema(conn):
    """
    Menangani migrasi tabel trades dan bot_state secara otomatis.
    """
    cur = conn.cursor()
    
    required_columns = {
        "id": "SERIAL PRIMARY KEY",
        "symbol": "VARCHAR(100)", 
        "side": "VARCHAR(10)", 
        "timeframe": "VARCHAR(5)", 
        "pattern": "VARCHAR(50)",
        "entry_price": "DECIMAL", 
        "sl_price": "DECIMAL", 
        "tp1": "DECIMAL", "tp2": "DECIMAL", "tp3": "DECIMAL",
        "rr": "DECIMAL",
        "status": "VARCHAR(50) DEFAULT 'Waiting Entry'", 
        "reason": "TEXT",
        "tech_score": "INT", 
        "quant_score": "INT", 
        "deriv_score": "INT", 
        "smc_score": "INT DEFAULT 0",
        "z_score": "DECIMAL DEFAULT 0", 
        "zeta_score": "DECIMAL DEFAULT 0", 
        "obi": "DECIMAL DEFAULT 0",
        "basis": "DECIMAL", 
        "btc_bias": "VARCHAR(50)",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", 
        "entry_hit_at": "TIMESTAMP", 
        "closed_at": "TIMESTAMP", 
        "exit_price": "DECIMAL", 
        "message_id": "VARCHAR(50)", 
        "channel_id": "VARCHAR(50)"
    }

    try:
        # 1. Check if table 'trades' exists
        cur.execute("SELECT to_regclass('public.trades');")
        if cur.fetchone()[0] is None:
            logger.info("🆕 Creating fresh 'trades' table...")
            cols = [f"{k} {v}" for k, v in required_columns.items()]
            cur.execute(f"CREATE TABLE trades ({', '.join(cols)});")
        else:
            # Check for missing columns
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'trades';")
            existing_cols = {row[0] for row in cur.fetchall()}
            
            missing_cols = []
            for col, dtype in required_columns.items():
                if col not in existing_cols:
                    # Clean type for ALTER command
                    clean_type = dtype.replace("SERIAL PRIMARY KEY", "INT").replace("PRIMARY KEY", "")
                    missing_cols.append(f"ADD COLUMN IF NOT EXISTS {col} {clean_type}")
            
            if missing_cols:
                logger.info(f"🛠️ Adding {len(missing_cols)} new columns to 'trades'...")
                cur.execute(f"ALTER TABLE trades {', '.join(missing_cols)};")

        # 2. Tambahan: Tabel 'active_trades' untuk Hyperliquid Bot (Execution side)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS active_trades (
                id SERIAL PRIMARY KEY,
                signal_id INT,
                symbol VARCHAR(20),
                side VARCHAR(10),
                entry_price DECIMAL,
                sl_price DECIMAL,
                tp1 DECIMAL, tp2 DECIMAL, tp3 DECIMAL,
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

        cur.execute("CREATE TABLE IF NOT EXISTS bot_state (key_name VARCHAR(50) PRIMARY KEY, value_text TEXT);")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration Failed: {e}")
        raise e
    finally:
        cur.close()

def get_conn():
    if DB_POOL is None:
        init_db()
    return DB_POOL.getconn()

def release_conn(conn):
    if DB_POOL and conn:
        DB_POOL.putconn(conn)

# Helper untuk mengambil sinyal aktif (dipakai di Scanner/Scanner.py)
def get_active_signals():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT symbol, timeframe FROM trades 
            WHERE status NOT ILIKE '%Closed%' 
            AND status NOT ILIKE '%Cancelled%'
            AND status NOT ILIKE '%Stop Loss%'
        """)
        return {(r[0], r[1]) for r in cur.fetchall()}
    except Exception as e:
        logger.warning(f"⚠️ Error fetching active signals: {e}")
        return set()
    finally:
        release_conn(conn)
