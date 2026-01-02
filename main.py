import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# Load the variables from .env into the environment
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Add a safety check
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Missing credentials! Ensure .env file is set up correctly.")

# Kraken Pair Names: BTC is 'XBT' in Kraken's system
PAIRS = {
    "XBTUSDC": "Bitcoin (BTC)",
    "ETHUSDC": "Ethereum (ETH)",
    "SOLUSDC": "Solana (SOL)"
}

def get_kraken_ohlc(pair, interval=1440):
    """Fetches daily OHLC data from Kraken."""
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    response = requests.get(url).json()
    
    if response.get("error"):
        print(f"Error fetching {pair}: {response['error']}")
        return None
    
    # Kraken returns the pair name as the key in the result
    # We find the key that isn't 'last'
    data_key = [k for k in response['result'].keys() if k != 'last'][0]
    raw_data = response['result'][data_key]
    
    # Columns: [time, open, high, low, close, vwap, volume, count]
    df = pd.DataFrame(raw_data, columns=[
        'time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
    ])
    
    # Convert types
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['close'] = df['close'].astype(float)
    return df

def send_telegram_msg(text):
    """Sends a message via Telegram bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def main():
    report_lines = ["*Market Update (Daily MAs)*\n"]
    
    for pair_code, display_name in PAIRS.items():
        df = get_kraken_ohlc(pair_code)
        if df is not None:
            # Calculate Moving Averages
            # 1D SMA is essentially the daily close
            df['SMA_1'] = df['close'].rolling(window=1).mean()
            df['SMA_7'] = df['close'].rolling(window=7).mean()
            df['SMA_30'] = df['close'].rolling(window=30).mean()
            
            # Get the most recent values (last row)
            latest = df.iloc[-1]
            
            line = (
                f"*{display_name}*\n"
                f"• 1D MA: ${latest['SMA_1']:.2f}\n"
                f"• 7D MA: ${latest['SMA_7']:.2f}\n"
                f"• 30D MA: ${latest['SMA_30']:.2f}\n"
            )
            report_lines.append(line)
    
    full_message = "\n".join(report_lines)
    print(full_message)

    # Commenting this for now while still in development (it does work though!)
    # send_telegram_msg(full_message)

if __name__ == "__main__":
    main()