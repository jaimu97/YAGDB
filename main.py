import sys
import openai
import re
import asyncio
import logging
import tiktoken
import json
import discord
from typing import Literal


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
            "global_settings": {
                "prompt_model": "gpt-3.5-turbo-16k",
                "prompt_system": "{Put your system prompt here!}",
                "prompt_max_tokens": 512,
                "logging_level": "INFO",
                "discord_intents": {
                    "guilds": True,
                    "members": True,
                    "emojis": True,
                    "messages": True,
                    "reactions": True
                },
                "bot_admins": []
            },
            "whitelist_servers": []
        }
        with open(file_name, "w") as settings_file:
            json.dump(settings, settings_file, indent=4)
        logging.critical(
            f"{file_name} not found! File \"{file_name}\" has been made as an example. Enter your settings and "
            f"restart the bot.")
        sys.exit(1)


def setup_logging(settings):
    """Set up logging level from global settings JSON."""
    logging.basicConfig(level=settings["global_settings"]["logging_level"])


def setup_intents(settings):
    """Set up Discord intents from global settings JSON."""
    intents = discord.Intents.default()
    intents_dict = settings["global_settings"]["discord_intents"]
    for intent_name, enabled in intents_dict.items():
        if hasattr(intents, intent_name):
            setattr(intents, intent_name, enabled)
    return intents


def count_tokens(text, enc):
    """Count the number of tokens in a text string."""
    return len(enc.encode(text))


async def prepare_message_history(current_message, settings, enc, client):
    """Prepare message history for the OpenAI API using the "chat" format (system, user, assistant)."""
    user_message = {
        "role": "user",
        "content": f"{current_message.author.name}#{current_message.author.discriminator}: "
                   f"{current_message.content}"
    }

    message_history = [
        {"role": "system", "content": f'{settings["global_settings"]["prompt_system"]}'},
        {"role": "user", "content": user_message["content"]}
    ]
    token_count = count_tokens(user_message["content"], enc)

    async for msg in current_message.channel.history(limit=100, oldest_first=False):
        if msg.author == client.user:
            role = "assistant"
            content = f"{msg.content}"
        else:
            role = "user"
            content = f"{msg.author.name}#{msg.author.discriminator}: {msg.content}"

        tokens = count_tokens(content, enc)

        if token_count + tokens + 1 < settings["global_settings"]["prompt_max_tokens"]:
            message_history.insert(0, {"role": role, "content": content})
            token_count += tokens + 1
        else:
            break

    return message_history, token_count


async def generate_response(message_history, current_message, settings):
    """Generate a response using the OpenAI API."""
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None,
                                          lambda: openai.ChatCompletion.create(
                                              model=settings["global_settings"]["prompt_model"],
                                              messages=message_history,
                                              max_tokens=settings["global_settings"]["prompt_max_tokens"],
                                              user=f"{current_message.author.name}#"
                                                   f"{current_message.author.discriminator}")
                                          )
    return response.choices[0].message.content.strip()


def remove_mentions(reply, current_message):
    """Remove any mentions if it's not to a person in this server."""
    server_members = [member.id for member in current_message.guild.members]
    for mention in re.findall(r"<@!?\d+>", reply):
        try:
            if int(mention[2:-1]) not in server_members:
                reply = reply.replace(mention, "")
        except ValueError:
            continue
        try:
            if int(mention[3:-1]) not in server_members:
                reply = reply.replace(mention, "")
        except ValueError as e:
            logging.error(f"Error occurred while removing mentions!\n{e}\nContinuing...")
            continue
    return reply


def main():
    api_keys = load_api_keys()
    openai.api_key = api_keys["openai_api_key"]
    discord_api_token = api_keys["discord_api_token"]
    settings = load_settings("settings.json")
    enc = tiktoken.encoding_for_model(settings["global_settings"]["prompt_model"])

    setup_logging(settings)

    intents = setup_intents(settings)

    client = discord.Client(intents=intents)
    tree = discord.app_commands.CommandTree(client)

    @client.event
    async def on_connect():
        logging.info("Connected to Discord!")

    @client.event
    async def on_ready():
        logging.info("Ready!")
        logging.debug("Syncing commands...")
        await tree.sync()
        logging.info(f'We have logged in as {client.user}')

    @tree.command(
        name="ping",
        description="Test if the bot is alive :))"
    )
    async def ping(ctx: discord.Interaction):
        logging.info(f"Pong! sent to: {ctx.user} in {ctx.guild}")
        await ctx.response.send_message("Pong!", ephemeral=True)

    @tree.command(
        name="set_prompt_system",
        description="Change the system prompt",
    )
    async def set_prompt_system(ctx: discord.Interaction, new_prompt: str):
        if ctx.user.id not in settings["global_settings"]["bot_admins"]:
            await ctx.response.send_message("You do not have permission to change the system prompt.")
            return
        settings["global_settings"]["prompt_system"] = new_prompt
        save_settings("settings.json", settings)
        await ctx.response.send_message(f"System prompt changed to: {new_prompt}")

    @tree.command(
        name="set_model",
        description="Change the model",
    )
    async def set_model(ctx: discord.Interaction, new_model: Literal[
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-0301",
        "gpt-4",
        "gpt-4-0613",
        "gpt-4-0314"
    ]):
        if ctx.user.id not in settings["global_settings"]["bot_admins"]:
            await ctx.response.send_message("You do not have permission to change the model.")
            return
        settings["global_settings"]["prompt_model"] = new_model
        save_settings("settings.json", settings)
        await ctx.response.send_message(f"Model changed to: `{new_model}`")

    @tree.command(
        name="set_channel",
        description="Sets current channel as the bot channel",
    )
    # TODO:

    @client.event
    async def on_message(current_message):
        if current_message.author == client.user:
            return
        if current_message.guild.id in settings["global_settings"]["whitelist_servers"]:
            try:
                logging.info(f"Received message: \"{current_message.content}\"")

                if not current_message.content.strip():
                    logging.error(f'Received a blank message form Discord')
                    return

                await current_message.channel.typing()

                message_history, token_count = await prepare_message_history(current_message, settings, enc, client)

                logging.info("Message history:")
                for msg in message_history:
                    logging.info(f"{msg['role']}: {msg['content']}")

                logging.info(f"Total token count: {token_count}")

                reply = await generate_response(message_history, current_message, settings)

                reply = remove_mentions(reply, current_message)

                if reply is None or reply.replace(" ", "") == "":
                    return

                logging.info(f"Generated text: {reply}")

                try:
                    if client.user.mentioned_in(current_message):
                        logging.info("Replying to message!")
                        await current_message.channel.send(reply, reference=current_message.to_reference())
                    else:
                        logging.info("Sending message!")
                        await current_message.channel.send(reply)
                except discord.errors.HTTPException:
                    logging.info("Message either too long or empty!")
            except Exception as e:
                logging.error(f"Got an error:\n{e}\nPlease try again later!")
                await current_message.response.send_message(f"Got an error:\n{e}\nPlease try again later!")
        else:
            logging.info(f"Received message from non-whitelisted server: \"{current_message.guild.id}\"\n"
                         f"(\"{current_message.guild.name}\")")

    client.run(token=discord_api_token)


if __name__ == "__main__":
    main()
