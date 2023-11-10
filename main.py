import openai
import discord
import logging
from api_keys import load_api_keys
from settings import load_settings
from discord_intents import setup_intents
from message_processing import (
    prepare_message_history,
    generate_response,
    get_encoding_for_model,
)
from commands import (
    set_prompt_system,
    set_model,
    set_channel,
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
        name="set_prompt_system",
        description="Change the system prompt",
    )
    async def set_prompt_system_command(ctx: discord.Interaction, new_prompt: str):
        await set_prompt_system(ctx, new_prompt, settings)

    @tree.command(
        name="set_model",
        description="Change the model",
    )
    async def set_model_command(ctx: discord.Interaction, new_model: str):
        await set_model(ctx, new_model, settings)

    @tree.command(
        name="set_channel",
        description="Sets current channel as the bot channel",
    )
    async def set_channel_command(ctx: discord.Interaction):
        await set_channel(ctx, settings)

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
                max_length = 2000
                reply_chunks = [reply[i:i + max_length] for i in range(0, len(reply), max_length)]

                last_messages = []
                for chunk in reply_chunks:
                    if chunk.strip():
                        message = await ctx.channel.send(chunk)
                        last_messages.append(message)
                    else:
                        logging.info("Skipping empty or whitespace-only message chunk.")

                await ctx.response.send_message("Regenerated response!", ephemeral=True)
            else:
                logging.info("Received empty reply from OpenAI! Skipping...")
        else:
            logging.error("No user message to regenerate.")
            await ctx.response.send_message("No user message to regenerate.", ephemeral=True)

    @discord_client.event
    async def on_message(current_message):
        global last_messages, last_user_message

        if current_message.author == discord_client.user:
            return
        if current_message.channel.id in settings["whitelist_channels"]:
            try:
                logging.info(f"Received message: \"{current_message.content}\"")

                if not current_message.content.strip():
                    logging.error(f'Received a blank message form Discord')
                    return

                await current_message.channel.typing()

                message_history, token_count = await prepare_message_history(current_message, settings, enc,
                                                                             discord_client)

                logging.info("Message history:")
                for msg in message_history:
                    logging.info(f"{msg['role']}: {msg['content']}")

                logging.info(f"Total token count: {token_count}")

                reply = await generate_response(message_history, current_message, settings, openai_client)

                if reply:
                    max_length = 2000
                    reply_chunks = [reply[i:i + max_length] for i in range(0, len(reply), max_length)]

                    last_messages = []  # Clear the list of last messages
                    for chunk in reply_chunks:
                        if chunk.strip():
                            if discord_client.user.mentioned_in(current_message):
                                message = await current_message.channel.send(chunk,
                                                                             reference=current_message.to_reference())
                            else:
                                message = await current_message.channel.send(chunk)
                            last_messages.append(message)  # Store the sent message
                        else:
                            logging.info("Skipping empty or whitespace-only message chunk.")
                else:
                    logging.info("Received empty reply from OpenAI! Skipping...")

                last_user_message = current_message

            except Exception as e:
                logging.error(f"Got an error:\n{e}\nPlease try again later!")
                await current_message.channel.send(f"Got an error:\n{e}\nPlease try again later!")

        else:
            logging.info(f"Received message from non-whitelisted server: \"{current_message.guild.id}\"\n"
                         f"(\"{current_message.guild.name}\"), skipping...")

    discord_client.run(token=discord_api_token)


if __name__ == "__main__":
    main()
