import json
import sys
import logging


def load_api_keys():
    """Load API keys from a JSON file. If the file doesn't exist, create a template."""
    try:
        with open("api_keys.json", "r") as api_keys_file:
            return json.load(api_keys_file)
    except FileNotFoundError:
        api_keys = {
            "openai_api_key": "PUT_KEY_HERE",
            "discord_api_token": "PUT_TOKEN_HERE"
        }
        with open("api_keys.json", "w") as api_keys_file:
            json.dump(api_keys, api_keys_file)

        logging.critical(
            "api_keys.json not found! File \"api_keys.json\n has been made as an example. Enter your API "
            "keys and restart the bot.")
        sys.exit(1)
