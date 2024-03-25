import requests
import asyncio
import pandas as pd

from apscheduler.schedulers.background import BackgroundScheduler
from soltrade.transactions import perform_swap, MarketPosition
from soltrade.indicators import calculate_ema, calculate_rsi, calculate_bbands
from soltrade.strategy import strategy, calc_stoploss, calc_trailing_stoploss
from soltrade.wallet import find_balance
from soltrade.log import log_general, log_transaction
from soltrade.config import config
from soltrade.tg_bot import send_info


# Stoploss and trading values for statistics and algorithm
stoploss = takeprofit = 0
ema_short = ema_medium = 0
upper_bb = lower_bb = 0
rsi = 0
price = 0


# Pulls the candlestick information in fifteen minute intervals
def fetch_candlestick():
    url = "https://min-api.cryptocompare.com/data/v2/histominute"
    headers = {'authorization': config().api_key}
    params = {'fsym': config().other_mint_symbol, 'tsym': 'USD', 'limit': 200, 'aggregate': config().trading_interval_minutes}
    response = requests.get(url, headers=headers, params=params)
    if response.json().get('Response') == 'Error':
        log_general.error(response.json().get('Message'))
        exit()
    return response.json()


# Analyzes the current market variables and determines trades
def perform_analysis():
    log_general.debug("Soltrade is analyzing the market; no trade has been executed.")

    global stoploss, trailing_stoploss, engage_tsl
    global entry_price

    # Converts JSON response for DataFrame manipulation
    candle_json = fetch_candlestick()
    candle_dict = candle_json["Data"]["Data"]

    # Creates DataFrame for manipulation
    columns = ['close', 'high', 'low', 'open', 'time']
    df = pd.DataFrame(candle_dict, columns=columns)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    df = strategy(df)
    print(df.tail(2))

    if not MarketPosition().position:
        usdc_balance = find_balance(config().usdc_mint)
        input_amount = round(usdc_balance, 1) - 0.01
        if df['entry'].iloc[-1] == 1:
            buy_msg = f"Soltrade has detected a buy signal using {input_amount} USDC"
            log_transaction.info(buy_msg)
            asyncio.run(send_info(buy_msg))
            # log_transaction.info(get_statistics())
            if input_amount <= 0 or input_amount >= usdc_balance:
                fund_msg = "Soltrade has detected a buy signal, but does not have enough USDC to trade."
                log_transaction.info(fund_msg)
                asyncio.run(send_info(fund_msg))
                return
            asyncio.run(perform_swap(input_amount, config().usdc_mint))
            df['entry_price'] = df['close'].iloc[-1]
            entry_price = df['entry_price']
            df = calc_stoploss(df)
            df = calc_trailing_stoploss(df)
            stoploss = df['stoploss'].iloc[-1]
            trailing_stoploss = df['trailing_stoploss'].iloc[-1]
            print(df.tail(2))
            # Save DataFrame to JSON file
            json_file_path = 'data.json'
            save_dataframe_to_json(df, json_file_path)

            
    else:        
    # Read DataFrame from JSON file
        df = read_dataframe_from_json(json_file_path)
        print(df.tail(2))
        input_amount = round(find_balance(config().other_mint), 1) - 0.01
        df = calc_trailing_stoploss(df)
        stoploss = df['stoploss'].iloc[-1]
        trailing_stoploss = df['trailing_stoploss'].iloc[-1]
        print(stoploss, trailing_stoploss)
        
        # Check Stoploss
        if df['close'].iloc[-1] <= stoploss:
            sl_msg = "Soltrade has detected a sell signal. Stoploss has been reached."
            log_transaction.info(sl_msg)
            asyncio.run(send_info(sl_msg))
            # log_transaction.info(get_statistics())
            asyncio.run(perform_swap(input_amount, config().other_mint))
            stoploss = takeprofit = 0
            df['entry_price'] = None

        # Check Trailing Stoploss
        if trailing_stoploss is not None:
            if df['close'].iloc[-1] < trailing_stoploss:
                tsl_msg = "Soltrade has detected a sell signal. Trailing stoploss has been reached."
                log_transaction.info(tsl_msg)
                asyncio.run(send_info(tsl_msg))
                # log_transaction.info(get_statistics())
                asyncio.run(perform_swap(input_amount, config().other_mint))
                stoploss = takeprofit = 0
                df['entry_price'] = None
            
        # Check Strategy
        if df['exit'].iloc[-1] == 1:
            exit_msg = "Soltrade has detected a sell signal from the strategy."
            log_transaction.info(exit_msg)
            asyncio.run(send_info(exit_msg))
            # log_transaction.info(get_statistics())
            asyncio.run(perform_swap(input_amount, config().other_mint))
            stoploss = takeprofit = 0
            df['entry_price'] = None


# This starts the trading function on a timer
def start_trading():
    output_message = "Soltrade has now initialized the trading algorithm."
    log_general.info(output_message)
    asyncio.run(send_info(output_message))
    log_general.debug("Available commands are /statistics, /pause, /resume, and /quit.")

    trading_sched = BackgroundScheduler()
    trading_sched.add_job(perform_analysis, 'interval', seconds=config().price_update_seconds, max_instances=1)
    trading_sched.start()
    perform_analysis()

    while True:
        event = input().lower()
        if event == '/pause':
            trading_sched.pause()
            log_general.info("Soltrade has now been paused.")

        if event == '/resume':
            trading_sched.resume()
            log_general.info("Soltrade has now been resumed.")
        if event == '/statistics':
            print_statistics()

        if event == '/quit':
            log_general.info("Soltrade has now been shut down.")
            exit()


def get_statistics():
    return f"""

Short EMA                           {ema_short}
Medium EMA                          {ema_medium}
Relative Strength Index             {rsi}
Price                               {price}
Upper Bollinger Band                {upper_bb.iat[-1]}
Lower Bollinger Band                {lower_bb.iat[-1]}"""


def print_statistics():
    log_general.debug(get_statistics())

# Function to save DataFrame to JSON file
def save_dataframe_to_json(df, file_path):
    df_json = df.to_json(orient='records')
    with open(file_path, 'w') as f:
        json.dump(df_json, f)

# Function to read DataFrame from JSON file
def read_dataframe_from_json(file_path):
    with open(file_path, 'r') as f:
        df_json = json.load(f)
    return pd.read_json(df_json)