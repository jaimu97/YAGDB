import openai
import discord
import logging
from typing import Literal
from api_keys import load_api_keys
from settings import save_settings, load_settings
from discord_intents import setup_intents
from message_processing import (
    prepare_message_history,
    generate_response,
    get_encoding_for_model,
)

last_messages = []
last_user_message = None


def setup_logging(settings):
    """Set up logging level from global settings JSON."""
    logging.basicConfig(level=settings["logging_level"])


def main():
    api_keys = load_api_keys()
    openai.api_key = api_keys["openai_api_key"]
    discord_api_token = api_keys["discord_api_token"]
    settings = load_settings("settings.json")
    enc = get_encoding_for_model(settings["prompt_model"])

    setup_logging(settings)

    intents = setup_intents(settings)

    openai_client = openai.OpenAI(api_key=openai.api_key)
    discord_client = discord.Client(intents=intents)

    tree = discord.app_commands.CommandTree(discord_client)

    @discord_client.event
    async def on_connect():
        logging.info("Connected to Discord!")

    @discord_client.event
    async def on_ready():
        logging.info("Ready!")
        logging.debug("Syncing commands...")
        await tree.sync()
        logging.info(f'We have logged in as {discord_client.user}')

    @tree.command(
        name="ping",
        description="Test if the bot is alive :))"
    )
    async def ping(ctx: discord.Interaction):
        logging.info(f"Pong! sent to: {ctx.user} in {ctx.guild}'s channel {ctx.channel}")
        await ctx.response.send_message("Pong!", ephemeral=True)

    @tree.command(
        name="set_system_prompt",
        description="Change the system prompt",
    )
    async def set_system_prompt(ctx: discord.Interaction, new_prompt: str):
        if ctx.user.id not in settings["bot_admins"]:
            await ctx.response.send_message("You do not have permission to change the system prompt!", ephemeral=True)
            return
        settings["system_prompt"] = new_prompt
        save_settings("settings.json", settings)
        await ctx.response.send_message(f"# System prompt changed!", ephemeral=True)

    @tree.command(
        name="set_model",
        description="Change the model",
    )
    async def set_model(ctx: discord.Interaction, new_model: Literal[
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-0301",
        "gpt-4",
        "gpt-4-1106-preview",
        "gpt-4-0613",
        "gpt-4-0314"
    ]):
        if ctx.user.id not in settings["bot_admins"]:
            await ctx.response.send_message("You do not have permission to change the model!", ephemeral=True)
            return
        settings["prompt_model"] = new_model
        save_settings("settings.json", settings)
        await ctx.response.send_message(f"Model changed to: `{new_model}`!", ephemeral=True)

    @tree.command(
        name="setup",
        description="Initial setup for the bot in the current channel",
    )
    async def setup_command(ctx: discord.Interaction):
        if ctx.user.id not in settings["bot_admins"]:
            await ctx.response.send_message("You do not have permission to setup the bot in this channel!",
                                            ephemeral=True)
            return
        if ctx.channel.id in settings["whitelist_channels"]:
            await ctx.response.send_message("This channel has already been set up!", ephemeral=True)
            return

        await ctx.response.defer(ephemeral=True)

        settings["whitelist_channels"].append(ctx.channel.id)
        save_settings("settings.json", settings)

        message_history = [
            {"role": "system", "content": f'Your name is {discord_client.user.name}. '
                                          f'{settings["system_prompt"]} '
                                          f'{settings["welcome_prompt"]}'}
        ]
        reply = await generate_response(message_history, ctx, settings, openai_client)

        if reply:
            await ctx.channel.send(reply)
        else:
            await ctx.followup.send("Oops! Something went wrong. Please try again later",
                                    ephemeral=True)
            return

        await ctx.followup.send(f"Channel \"{ctx.channel.name}\" has been set up and is now ready for use!",
                                ephemeral=True)

    @tree.command(
        name="regenerate",
        description="Delete the last reply made by the bot and generate a new one",
    )
    async def regenerate_command(ctx: discord.Interaction):
        global last_messages
        global last_user_message

        for message in last_messages:
            await message.delete()

        if last_user_message is not None:
            message_history, token_count = await prepare_message_history(last_user_message, settings, enc,
                                                                         discord_client)
            reply = await generate_response(message_history, last_user_message, settings, openai_client)

            if reply:
                last_messages = await send_reply_chunks(ctx, reply)
                await ctx.response.send_message("Regenerated response!", ephemeral=True)
            else:
                logging.info("Received empty reply from OpenAI! Skipping...")
        else:
            logging.error("No user message to regenerate.")
            await ctx.response.send_message("No user message to regenerate.", ephemeral=True)

    @tree.command(
        name="reply",
        description="Prompt the bot to reply to a message",
    )
    async def reply_command(ctx: discord.Interaction):
        global last_messages, last_user_message

        await ctx.response.defer(ephemeral=True)

        message_history, token_count = await prepare_message_history(ctx, settings, enc, discord_client)

        logging.info("Message history:")
        for msg in message_history:
            logging.info(f"{msg['role']}: {msg['content']}")

        logging.info(f"Total token count: {token_count}")

        reply = await generate_response(message_history, ctx, settings, openai_client)

        if reply:
            last_messages = await send_reply_chunks(ctx, reply)
        else:
            logging.info("Received empty reply from OpenAI! Skipping...")

        last_user_message = ctx
        await ctx.followup.send("Replied to the message!", ephemeral=True)

    async def send_reply_chunks(ctx, reply):
        max_length = 2000
        reply_chunks = [reply[i:i + max_length] for i in range(0, len(reply), max_length)]

        last_messages = []
        for chunk in reply_chunks:
            if chunk.strip():
                message = await ctx.channel.send(chunk)
                last_messages.append(message)
            else:
                logging.info("Skipping empty or whitespace-only message chunk.")
        return last_messages

    discord_client.run(token=discord_api_token)


if __name__ == "__main__":
    main()
