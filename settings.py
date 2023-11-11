import json
import sys
import logging


def save_settings(file_name, settings):
    """Save settings to a JSON file."""
    with open(file_name, "w") as file:
        json.dump(settings, file, indent=4)


def load_settings(file_name):
    """Loads settings JSON, if it doesn't exist, create a template."""
    try:
        with open(file_name, "r") as settings_file:
            return json.load(settings_file)
    except FileNotFoundError:
        settings = {
            "prompt_model": "gpt-3.5-turbo-16k",
            "system_prompt": "{Put your system prompt here!}",
            "welcome_prompt": "{Put your welcome prompt here!}",
            "prompt_max_tokens": 512,
            "logging_level": "INFO",
            "discord_intents": {
                "guilds": True,
                "members": True,
                "emojis": True,
                "messages": True,
                "message_content": True,
                "reactions": True
            },
            "bot_admins": [],
            "whitelist_channels": []
        }
        with open(file_name, "w") as settings_file:
            json.dump(settings, settings_file, indent=4)
        logging.critical(
            f"{file_name} not found! File \"{file_name}\" has been made as an example. Enter your settings and "
            f"restart the bot.")
        sys.exit(1)
