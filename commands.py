import discord
from settings import save_settings


async def set_prompt_system(ctx: discord.Interaction, new_prompt: str, settings):
    if ctx.user.id not in settings["bot_admins"]:
        await ctx.response.send_message("You do not have permission to change the system prompt!", ephemeral=True)
        return
    settings["prompt_system"] = new_prompt
    save_settings("settings.json", settings)
    await ctx.response.send_message(f"# System prompt changed!", ephemeral=True)


async def set_model(ctx: discord.Interaction, new_model: str, settings):
    if ctx.user.id not in settings["bot_admins"]:
        await ctx.response.send_message("You do not have permission to change the model!", ephemeral=True)
        return
    settings["prompt_model"] = new_model
    save_settings("settings.json", settings)
    await ctx.response.send_message(f"Model changed to: `{new_model}`!", ephemeral=True)


async def set_channel(ctx: discord.Interaction, settings):
    if ctx.user.id not in settings["bot_admins"]:
        await ctx.response.send_message("You do not have permission to change the bot channel!", ephemeral=True)
        return
    if ctx.channel.id in settings["whitelist_channels"]:
        await ctx.response.send_message("This channel is already the bot channel!", ephemeral=True)
        return
    settings["whitelist_channels"].append(ctx.channel.id)
    save_settings("settings.json", settings)
    await ctx.response.send_message(f"Added {ctx.channel.name} to the whitelist!", ephemeral=True)
