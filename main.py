import requests
import pandas as pd
import os
from dotenv import load_dotenv
from enum import Enum

# Load the variables from .env into the environment
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# If these are not properly defined as floats, this will intentionally break.
# TODO: Not used yet
FLAT_THRESHOLD_1D = float(os.getenv("FLAT_THRESHOLD_1D")) # pyright: ignore[reportArgumentType]
FLAT_THRESHOLD_7D = float(os.getenv("FLAT_THRESHOLD_7D")) # pyright: ignore[reportArgumentType]
FLAT_THRESHOLD_30D = float(os.getenv("FLAT_THRESHOLD_30D")) # pyright: ignore[reportArgumentType]

class MATypes(Enum):
    MA1D = 1
    MA7D = 2
    MA30D = 3

class MoveType(Enum):
    UP = 1
    FLAT = 0
    DOWN = -1

class Actions(Enum):
    BUYBIG = 2
    BUYSMALL = 1
    HOLD = 0
    SELLSMALL = -1
    SELLBIG = -2

INTERPRETATION_30_7_1 = {
    MoveType.UP: {
        MoveType.UP: {
            MoveType.UP: Actions.BUYSMALL
            , MoveType.FLAT: Actions.HOLD
            , MoveType.DOWN: Actions.SELLSMALL
        }
        , MoveType.FLAT: {
            MoveType.UP: Actions.BUYBIG
            , MoveType.FLAT: Actions.HOLD
            , MoveType.DOWN: Actions.SELLSMALL
        }
        , MoveType.DOWN: {
            MoveType.UP: Actions.BUYSMALL
            , MoveType.FLAT: Actions.SELLSMALL
            , MoveType.DOWN: Actions.SELLBIG
        }
    }
    , MoveType.FLAT: {
        MoveType.UP: {
            MoveType.UP: Actions.BUYSMALL
            , MoveType.FLAT: Actions.SELLSMALL
            , MoveType.DOWN: Actions.HOLD
        }
        , MoveType.FLAT: {
            MoveType.UP: Actions.BUYSMALL
            , MoveType.FLAT: Actions.HOLD
            , MoveType.DOWN: Actions.SELLSMALL
        }
        , MoveType.DOWN: {
            MoveType.UP: Actions.SELLBIG
            , MoveType.FLAT: Actions.SELLSMALL
            , MoveType.DOWN: Actions.SELLBIG
        }
    }
    , MoveType.DOWN: {
        MoveType.UP: {
            MoveType.UP: Actions.BUYBIG
            , MoveType.FLAT: Actions.HOLD
            , MoveType.DOWN: Actions.SELLBIG
        }
        , MoveType.FLAT: {
            MoveType.UP: Actions.SELLSMALL
            , MoveType.FLAT: Actions.SELLSMALL
            , MoveType.DOWN: Actions.SELLBIG
        }
        , MoveType.DOWN: {
            MoveType.UP: Actions.SELLBIG
            , MoveType.FLAT: Actions.SELLBIG
            , MoveType.DOWN: Actions.SELLBIG
        }
    }
}

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

def evaluate_MA(type: MATypes, value: float) -> MoveType:
    if (type==MATypes.MA1D and abs(value) < FLAT_THRESHOLD_1D) \
            or (type==MATypes.MA7D and abs(value) < FLAT_THRESHOLD_7D) \
            or (type==MATypes.MA30D and abs(value) < FLAT_THRESHOLD_30D):
        return MoveType.FLAT
    elif value < 0:
        return MoveType.DOWN
    else:
        return MoveType.UP

def interpret_MA_moves(differences: dict) -> Actions:
    MA_1D_move = evaluate_MA(MATypes.MA1D, differences["SMA_1_diff"])
    MA_7D_move = evaluate_MA(MATypes.MA7D, differences["SMA_7_diff"])
    MA_30D_move = evaluate_MA(MATypes.MA30D, differences["SMA_30_diff"])

    return INTERPRETATION_30_7_1[MA_30D_move][MA_7D_move][MA_1D_move]

def perc_diff_report(diff: float) -> str:
    """
    Do formatting rounding, but more importantly prefix positive numbers with a plus.
    
    :param diff: Percentage difference
    :type diff: float
    :return: +{diff}% with 1 decimal if diff is positive, -{diff}% if negative.
    :rtype: str
    """
    return f"+{round(diff, 1)}%" if diff >= 0 else f"{round(diff, 1)}%"

def perform_analysis(kraken_dataframe: pd.DataFrame):
    # Calculate Moving Averages
    # 1D SMA is just the daily close
    df = kraken_dataframe.copy()
    df['SMA_7'] = df['close'].rolling(window=7).mean()
    df['SMA_30'] = df['close'].rolling(window=30).mean()
    
    return df

def determine_action(today_data: pd.Series, yesterday_data: pd.Series):
    # Get the most recent and 2nd most recent values (last 2 rows)

    differences = {
        "SMA_1_diff": perc_diff(today_data['close'], yesterday_data['close'])
        , "SMA_7_diff": perc_diff(today_data['SMA_7'], yesterday_data['SMA_7'])
        , "SMA_30_diff": perc_diff(today_data['SMA_30'], yesterday_data['SMA_30'])
    }

    action = interpret_MA_moves(differences)

    # Action is really the interesting one, the rest is returned for information purposes
    return {'action': action, 'differences': differences}

def create_report_entry(display_name: str, values_today: pd.Series, differences: dict, action: Actions) -> str:
    line = (
                f"*{display_name}*\n"
                f"• 1D MA: ${values_today['close']:.2f} ({perc_diff_report(differences['SMA_1_diff'])})\n"
                f"• 7D MA: ${values_today['SMA_7']:.2f} ({perc_diff_report(differences['SMA_7_diff'])})\n"
                f"• 30D MA: ${values_today['SMA_30']:.2f} ({perc_diff_report(differences['SMA_30_diff'])})\n"
                f"Interpretation: {action.name}\n"
            )
    return line

def main():
    report_lines = ["*Market Update (Daily MAs)*\n"]
    
    for pair_code, display_name in PAIRS.items():
        df = get_kraken_ohlc(pair_code)
        if df is not None:
            df_with_analysis = perform_analysis(df)

            today = df_with_analysis.iloc[-1]
            yesterday = df_with_analysis.iloc[-2]

            result = determine_action(today, yesterday)

            action = result['action']
            differences = result['differences']

            report_lines.append(create_report_entry(display_name, today, differences, action))

            # For debugging/price logging purposes, since Kraken only gives at most 720 points
            # filename = f'{pair_code}_{df.iloc[-1]['time'].date()}_{df.iloc[0]['time'].date()}.csv'
            # df.to_csv(filename, header=True)

    full_message = "\n".join(report_lines)
    print(full_message)

    # Commenting this for now while still in development (it does work though!)
    # send_telegram_msg(full_message)

if __name__ == "__main__":
    main()