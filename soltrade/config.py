import os
import json
import base58

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from soltrade.log import log_general


class Config:
    def __init__(self, path):
        self.path = path
        self.api_key = None
        self.private_key = None
        self.custom_rpc_https = None
        self.usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.sol_mint = "So11111111111111111111111111111111111111112"
        self.other_mint = None
        self.other_mint_symbol = None
        self.price_update_seconds = None
        self.trading_interval_minutes = None
        self.slippage = None  # BPS
        self.computeUnitPriceMicroLamports = None
        self.stoploss = None
        self.trailing_stoploss = None
        self.trailing_stoploss_target = None
        self.telegram = None
        self.tg_bot_token = None
        self.tg_bot_uid = None
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.path):
            log_general.error(
                "Soltrade was unable to detect the JSON file. Are you sure config.json has not been renamed or removed?")
            exit(1)

        with open(self.path, 'r') as file:
            try:
                config_data = json.load(file)
                self.api_key = config_data["api_key"]
                self.private_key = config_data["private_key"]
                self.custom_rpc_https = config_data.get("custom_rpc_https") or "https://api.mainnet-beta.solana.com/"
                self.other_mint = config_data.get("other_mint", "")
                self.other_mint_symbol = config_data.get("other_mint_symbol", "UNKNOWN")
                self.price_update_seconds = int(config_data.get("price_update_seconds", 60))
                self.trading_interval_minutes = int(config_data.get("trading_interval_minutes", 1))
                self.slippage = int(config_data.get("slippage", 50))
                self.computeUnitPriceMicroLamports = int(config_data.get("computeUnitPriceMicroLamports", 20 * 14000))  # default fee of roughly $.04 today
                self.verbose = config_data.get("verbose", False)
                self.strategy = config_data.get("strategy", "default")
                self.stoploss = config_data["stoploss"]
                self.trailing_stoploss = config_data["trailing_stoploss"]
                self.trailing_stoploss_target = config_data["trailing_stoploss_target"]
                self.telegram = config_data.get("telegram", False)
                if self.telegram == True:
                    self.tg_bot_token = config_data["tg_bot_token"]
                    self.tg_bot_uid = config_data["tg_bot_uid"]
                # print(len(self.private_key), self.private_key)
            except json.JSONDecodeError as e:
                log_general.error(f"Error parsing JSON: {e}")
                exit(1)
            except KeyError as e:
                log_general.error(f"Missing configuration key: {e}")
                exit(1)

    @property
    def keypair(self):
        try:
            b58_string = self.private_key
            keypair = Keypair.from_base58_string(b58_string)
            # print(f"Using Wallet: {keypair.pubkey()}")

            return keypair
        except Exception as e:
            log_general.error(f"Error decoding private key: {e}")
            exit(1)

    @property
    def public_address(self):
        return self.keypair.pubkey()

    @property
    def client(self):
        rpc_url = self.custom_rpc_https
        return Client(rpc_url)
    
    @property
    def decimals(self):
        response = self.client.get_account_info_json_parsed(Pubkey.from_string(config().other_mint)).to_json()
        json_response = json.loads(response)
        value = 10**json_response["result"]["value"]["data"]["parsed"]["info"]["decimals"]
        return value


_config_instance = None


def config(path=None):
    global _config_instance
    if _config_instance is None and path is not None:
        _config_instance = Config(path)
    return _config_instance
