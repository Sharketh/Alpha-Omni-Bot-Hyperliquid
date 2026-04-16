import asyncio
from modules.connection import get_hl_client
from modules.technicals import analyze_market
from modules.execution import place_trade

async def run_alpha_omni():
    info, exchange = get_hl_client()
    print("Alpha Omni Bot: Connected to Hyperliquid")

    while True:
        try:
            # 1. Auto-Screening Universe
            meta = info.meta()
            universe = [a['name'] for a in meta['universe']]
            
            for asset in universe:
                # 2. Get Market Data (L2 Book / Candles)
                candles = info.candle_snapshot(asset, "15m")
                
                # 3. Decision Logic
                signal = analyze_market(candles)
                
                if signal == "BUY":
                    await place_trade(exchange, asset, "long")
                elif signal == "SELL":
                    await place_trade(exchange, asset, "short")
            
            await asyncio.sleep(60) # Scan every minute
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_alpha_omni())
