import asyncio
import tiktoken
import uuid
from typing import Tuple


def count_tokens(text, enc):
    """Count the number of tokens in a text string."""
    return len(enc.encode(text))


def get_encoding_for_model(model):
    """Get the encoding for a given model."""
    return tiktoken.encoding_for_model(model)


async def prepare_message_history(interaction, settings, enc, client) -> Tuple:
    """Prepare message history for the OpenAI API using the "chat" format (system, user, assistant)."""
    user_message = {
        "role": "user",
        "content": f"{interaction.user.name}: {interaction.data.get('content', '')}"
    }

    message_history = [
        {"role": "system", "content": f'{settings["system_prompt"]}'}
    ]
    token_count = count_tokens(user_message["content"], enc)

    async for msg in interaction.channel.history(limit=100, oldest_first=False):
        if msg.id == interaction.id:
            continue
        if msg.author == client.user:
            role = "assistant"
            content = f"{msg.clean_content}"
        else:
            role = "user"
            content = f"{msg.author.name}: {msg.clean_content}"

        tokens = count_tokens(content, enc)

        if token_count + tokens + 1 < settings["prompt_max_tokens"]:
            message_history.insert(1, {"role": role, "content": content})
            token_count += tokens + 1
        else:
            break

    message_history.append(user_message)
    return message_history, token_count


async def generate_response(message_history, interaction, settings, client):
    """Generate a response using the OpenAI API."""
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=settings["prompt_model"],
            messages=message_history,
            temperature=0.7,
            top_p=0.9,
            max_tokens=settings["prompt_max_tokens"],
            user=f"{interaction.user.name}.{uuid.uuid4()}"
        ),
    )
    return response.choices[0].message.content.strip()
