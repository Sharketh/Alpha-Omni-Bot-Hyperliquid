import json
import os
import logging
from dotenv import load_dotenv

# Setup logging sederhana untuk loader
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConfigLoader")

load_dotenv()

def load_config():
    config_path = 'config.json'
    
    if not os.path.exists(config_path):
        logger.warning(f"⚠️ {config_path} tidak ditemukan! Menggunakan default/env saja.")
        config = {}
    else:
        with open(config_path, 'r') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"❌ Gagal membaca {config_path}. Format JSON salah.")
                config = {}

    # Pengaturan Database berdasarkan Environment
    if os.getenv('BOT_ENV') == 'testing':
        logger.info("🛠️ MODE TESTING AKTIF: Menggunakan database test.")
        # Memastikan dictionary database ada sebelum diakses
        if 'database' not in config:
            config['database'] = {}
        config['database']['database'] = 'bybit_bot_test' # atau hl_bot_test
        
    # Inject API Keys dari .env ke dalam objek CONFIG (Opsional tapi rapi)
    if 'api' not in config:
        config['api'] = {}
        
    config['api']['hl_address'] = os.getenv('HL_ACCOUNT_ADDRESS')
    config['api']['hl_private_key'] = os.getenv('HL_PRIVATE_KEY')

    return config

CONFIG = load_config()
