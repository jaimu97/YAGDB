import discord


# Sorry if this is a bit ugly, not so familiar with classes in Python.
class UIHandler:
    def __init__(self):
        self.message_id_to_view = {}

    async def send_message_with_view(self, channel, content, view):
        message = await channel.send(content, view=view)
        self.message_id_to_view[message.id] = view

    @staticmethod
    def create_button_view(label, style, custom_id, callback):
        view = discord.ui.View()
        button = discord.ui.Button(label=label, style=style, custom_id=custom_id)
        button.callback = callback
        view.add_item(button)
        return view

    async def on_interaction(self, interaction):
        if interaction.data and interaction.data.get('component_type') == discord.ComponentType.button:
            # TODO: Save button id so that when the bot restarts, it can still respond to the button.
            custom_id = interaction.data.get('custom_id')
            # Probably don't need whitelist check since the button always comes from the bot which should've sent the
            # button in a whitelisted channel anyway?
            view = self.message_id_to_view.get(interaction.message.id)
            if view:
                for item in view.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
                        if item.callback:
                            await item.callback(interaction)
                            break
            else:
                await interaction.response.send_message("This button is no longer active.", ephemeral=True)


# TODO: button callback, somehow need to connect this to the bot too. Maybe save the response in a variable and then
#       prompt the next message as {button_clicker_user} does {button_interaction} or something and have the AI
#       generate an explanation along with the button's text?
async def example_button_callback(interaction):
    await interaction.response.send_message("Button clicked!", ephemeral=True)
