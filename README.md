Alpha-Omni-Bot-Hyperliquid 🚀
Alpha-Omni-Bot adalah sistem perdagangan algoritma otonom yang dirancang khusus untuk ekosistem Hyperliquid L1. Bot ini menggabungkan analisis struktur pasar tingkat lanjut (SMC), metrik kuantitatif, dan pengenalan pola teknis untuk mengidentifikasi peluang trading dengan probabilitas tinggi.

📌 Fitur Utama
SMC Engine: Deteksi otomatis Market Structure Break (MSB), Change of Character (CHoCH), dan validasi Order Blocks.

Quantitative Metrics: Analisis Relative Volume (RVOL), Order Book Imbalance (OBI), dan Z-Score untuk mendeteksi anomali harga.

Pattern Recognition: Algoritma pendeteksi pola Chart (Double Top/Bottom, Bull/Bear Flags, Triangles).

Fibonacci-Based Entry: Penentuan titik entri, Stop Loss (SL), dan Take Profit (TP) menggunakan rasio Fibonacci yang presisi.

Hyperliquid Integration: Koneksi langsung ke Hyperliquid L1 menggunakan ccxt dengan latensi rendah.

Multi-Channel Alerts: Notifikasi real-time dan dashboard status melalui Discord Webhooks.

Database Persistent: Penyimpanan sinyal aktif dan riwayat trading menggunakan PostgreSQL.

📂 Struktur Proyek
Plaintext
Alpha-Omni-Bot-Hyperliquid/
├── main.py                 # Core Orchestrator (Main Loop)
├── config.json             # Konfigurasi strategi & API
├── .env                    # Rahasia/Kredensial (Private Keys, DB Pass)
├── requirements.txt        # Dependensi Python
├── /modules
│   ├── smc.py              # Logika Smart Money Concepts
│   ├── quant.py            # Analisis Volatilitas & Volume
│   ├── technicals.py       # Indikator teknis & Divergence
│   ├── derivatives.py      # Data Funding & Basis
│   ├── database.py         # Manajemen PostgreSQL & Sinyal Aktif
│   └── discord_bot.py      # Alerting & Dashboard System
└── /deploy
    ├── bot.service         # Systemd unit file untuk VPS
    └── restart_bot.sh      # Script otomasi restart

🛠 Instalasi & Persiapan
1. Prasyarat
Python 3.10+

PostgreSQL Database

Hyperliquid Wallet (Disarankan menggunakan API Wallet/Signing Wallet)

2. Kloning Repositori
Bash
git clone https://github.com/Sharketh/Alpha-Omni-Bot-Hyperliquid.git
cd Alpha-Omni-Bot-Hyperliquid

3. Instal Dependensi
Bash
pip install -r requirements.txt

4. Konfigurasi Lingkungan
Buat file .env di direktori utama:

Cuplikan kode
HL_ACCOUNT_ADDRESS=0xAlamatWalletAnda
HL_PRIVATE_KEY=0xPrivateKeyAnda
DB_PASSWORD=PasswordPostgresAnda
Sesuaikan parameter strategi di config.json terutama bagian discord_webhook dan trading_params.

🚀 Menjalankan Bot
Mode Pengembangan:

Bash
python main.py

Mode Produksi (Linux VPS):

Salin file service: cp deploy/bot.service /etc/systemd/system/
Aktifkan service:

Bash
systemctl enable bot.service
systemctl start bot.service

📊 Strategi Alpha-Omni
Bot ini bekerja dengan alur Filter-Score-Execute:

Market Bias: Mengecek trend BTC (EMA 13/21).

Scanning: Mencari pola chart pada daftar koin Hyperliquid.

Validation: Menguji sinyal dengan skor SMC (min. 5) dan metrik Quant (min. 3).

Risk Management: Menghitung Risk/Reward ratio (minimal 1:3).

⚠️ Disclaimer
Trading aset kripto melibatkan risiko tinggi. Bot ini disediakan untuk tujuan pendidikan dan alat bantu analisis. Pengembang tidak bertanggung jawab atas kerugian finansial yang terjadi akibat penggunaan perangkat lunak ini. Gunakan risiko Anda sendiri (DYOR).

📝 Lisensi
Proyek ini dilisensikan di bawah MIT License - lihat file LICENSE untuk detailnya.
