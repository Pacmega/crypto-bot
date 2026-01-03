import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# Load the variables from .env into the environment
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# If these are not properly defined as floats, this will intentionally break.
# TODO: Not used yet
FLAT_THRESHOLD_1D = float(os.getenv("FLAT_THRESHOLD_1D")) # pyright: ignore[reportArgumentType]
FLAT_THRESHOLD_7D = float(os.getenv("FLAT_THRESHOLD_7D")) # pyright: ignore[reportArgumentType]
FLAT_THRESHOLD_30D = float(os.getenv("FLAT_THRESHOLD_30D")) # pyright: ignore[reportArgumentType]

INTERPRETATION = {
    "30D UP": {
        "7D UP": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D FLAT": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D DOWN": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
    }
    , "30D FLAT": {
        "7D UP": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D FLAT": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D DOWN": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
    }
    , "30D DOWN": {
        "7D UP": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D FLAT": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
        , "7D DOWN": {
            "1D UP": "placeholder"
            , "1D FLAT": "placeholder"
            , "1D DOWN": "placeholder"
        }
    }
}

print(FLAT_THRESHOLD_1D)

exit(0)



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

def perc_diff(new_val: float, old_val: float) -> float:
    return (new_val / old_val - 1) * 100

def perc_diff_report(diff: float) -> str:
    """
    Do formatting rounding, but more importantly prefix positive numbers with a plus.
    
    :param diff: Percentage difference
    :type diff: float
    :return: +{diff}% with 1 decimal if diff is positive, -{diff}% if negative.
    :rtype: str
    """
    return f"+{round(diff, 1)}%" if diff >= 0 else f"{round(diff, 1)}%"

def main():
    report_lines = ["*Market Update (Daily MAs)*\n"]
    
    for pair_code, display_name in PAIRS.items():
        df = get_kraken_ohlc(pair_code)
        if df is not None:
            # Calculate Moving Averages
            # 1D SMA is just the daily close
            df['SMA_7'] = df['close'].rolling(window=7).mean()
            df['SMA_30'] = df['close'].rolling(window=30).mean()
            
            # Get the most recent and 2nd most recent values (last 2 rows)
            today = df.iloc[-1]
            yesterday = df.iloc[-2]

            differences = {
                "SMA_1_diff": perc_diff_report(perc_diff(today['close'], yesterday['close']))
                , "SMA_7_diff": perc_diff_report(perc_diff(today['SMA_7'], yesterday['SMA_7']))
                , "SMA_30_diff": perc_diff_report(perc_diff(today['SMA_30'], yesterday['SMA_30']))
            }
            
            line = (
                f"*{display_name}*\n"
                f"• 1D MA: ${today['SMA_1']:.2f} ({differences['SMA_1_diff']})\n"
                f"• 7D MA: ${today['SMA_7']:.2f} ({differences['SMA_7_diff']})\n"
                f"• 30D MA: ${today['SMA_30']:.2f} ({differences['SMA_30_diff']})\n"
            )
            report_lines.append(line)
    
    full_message = "\n".join(report_lines)
    print(full_message)

    # Commenting this for now while still in development (it does work though!)
    # send_telegram_msg(full_message)

if __name__ == "__main__":
    main()