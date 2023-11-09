import discord


def setup_intents(settings):
    """Set up Discord intents from global settings JSON."""
    intents = discord.Intents.default()
    intents_dict = settings["discord_intents"]
    for intent_name, enabled in intents_dict.items():
        if hasattr(intents, intent_name):
            setattr(intents, intent_name, enabled)
    return intents
