import os
import discord
from discord.ext import commands
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Discord bot
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
BOT_NAME = os.getenv('BOT_NAME', 'General Brasch')
MESSAGE_HISTORY_LIMIT = int(os.getenv('MESSAGE_HISTORY_LIMIT', 10))

# Configure OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set up Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True  # Enable members intent
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def on_ready():
    """Event triggered when the bot is ready and connected to Discord."""
    print(f'{bot.user.name} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print(f'Bot ID: {bot.user.id}')
    print(f'Bot Application ID: {DISCORD_APPLICATION_ID}')

@bot.event
async def on_message(message):
    """Event triggered when a message is sent in a channel the bot can see."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Check if the bot is mentioned in the message
    if bot.user.mentioned_in(message):
        # Remove the mention from the message content
        content = message.content
        for mention in message.mentions:
            content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if content:
            # Show typing indicator while processing
            async with message.channel.typing():
                try:
                    # Get message history for context
                    message_history = await get_message_history(message.channel, message, MESSAGE_HISTORY_LIMIT)
                    
                    # Call OpenAI API to generate a response with context
                    response = await generate_response(content, message_history)
                    
                    # Send the response
                    await message.reply(response)
                except Exception as e:
                    print(f"Error generating response: {e}")
                    await message.reply("I'm sorry, I encountered an error while processing your request.")
    
    # Process commands
    await bot.process_commands(message)

async def get_message_history(channel, current_message, limit):
    """Get the message history from the channel for context."""
    messages = []
    async for msg in channel.history(limit=limit + 1, before=current_message):
        # Skip messages from the bot itself
        if msg.author == bot.user:
            continue
        
        # Format the message with author and content
        messages.append({
            "role": "user" if msg.author != bot.user else "assistant",
            "name": str(msg.author.display_name),
            "content": msg.content
        })
    
    # Reverse the messages to get them in chronological order
    messages.reverse()
    return messages

async def generate_response(prompt, message_history):
    """Generate a response using OpenAI's API with message history context."""
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": f"You are {BOT_NAME}, a helpful assistant in a Discord server. You respond to questions when tagged in messages. Be concise, helpful, and friendly."}
        ]
        
        # Add message history for context
        if message_history:
            messages.extend(message_history)
        
        # Add the current prompt
        messages.append({"role": "user", "content": prompt})
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You can change this to a different model
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        # Extract and return the response text
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API error: {e}")
        raise

def main():
    """Main function to run the bot."""
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    main()
