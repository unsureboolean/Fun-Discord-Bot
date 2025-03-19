import os
import discord
from discord.ext import commands
from discord import app_commands
import openai
import re
import json
from dotenv import load_dotenv
from personas import personas, default_persona
from database import Database

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

# Initialize database
db = Database("data/bot_data.db")

# Dictionary to cache server data to reduce database queries
server_cache = {}

def get_server_data(guild_id):
    """Get or initialize server-specific data."""
    # Check cache first
    if guild_id in server_cache:
        return server_cache[guild_id]
    
    # Get from database
    server_data = db.get_server_data(guild_id, default_persona)
    
    # Cache for future use
    server_cache[guild_id] = server_data
    
    return server_data

@bot.event
async def on_ready():
    """Event triggered when the bot is ready and connected to Discord."""
    print(f'{bot.user.name} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print(f'Bot ID: {bot.user.id}')
    print(f'Bot Application ID: {DISCORD_APPLICATION_ID}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="persona", description="Change the bot's persona")
@app_commands.describe(persona_choice="Choose the bot's persona")
@app_commands.choices(persona_choice=[
    app_commands.Choice(name=persona_info["name"], value=persona_key)
    for persona_key, persona_info in personas.items()
])
async def change_persona(interaction: discord.Interaction, persona_choice: str):
    """Slash command to change the bot's persona."""
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    # Get server data
    server = get_server_data(interaction.guild_id)
    
    # Update server's persona
    if persona_choice in personas:
        old_persona = server['persona']
        server['persona'] = persona_choice
        
        # Update in database
        db.update_server_persona(interaction.guild_id, persona_choice)
        
        # Change bot's nickname in the server
        try:
            await interaction.guild.me.edit(nick=personas[persona_choice]["nickname"])
            await interaction.response.send_message(
                f"Persona changed from '{personas[old_persona]['name']}' to '{personas[persona_choice]['name']}'.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Persona changed to '{personas[persona_choice]['name']}', but I don't have permission to change my nickname.",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(f"Unknown persona: {persona_choice}", ephemeral=True)

@bot.event
async def on_message(message):
    """Event triggered when a message is sent in a channel the bot can see."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Ignore messages in DMs
    if message.guild is None:
        return
    
    # Check if the bot was mentioned
    if bot.user in message.mentions:
        # Get the content without the mention
        content = re.sub(r'<@!?[0-9]+>', '', message.content).strip()
        
        # If there's actual content after removing the mention
        if content:
            try:
                # Get server data
                server = get_server_data(message.guild.id)
                
                # Get message history for context
                message_history = await get_message_history(message.channel, message, MESSAGE_HISTORY_LIMIT, server)
                
                # Generate response with context
                response = await generate_response(content, message_history, server['persona'])
                
                # Store the interaction in chat history
                store_message(server, message.guild.id, message.channel.id, "user", message.author.display_name, content)
                store_message(server, message.guild.id, message.channel.id, "assistant", bot.user.display_name, response)
                
                # Send the response
                await message.reply(response)
            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                print(error_msg)
                await message.reply("I'm sorry, I encountered an error while processing your request.")
    
    # Process commands
    await bot.process_commands(message)

def sanitize_name(name):
    """Sanitize a username to ensure it matches OpenAI's pattern requirement."""
    # Replace any non-alphanumeric, underscore, or hyphen characters
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', str(name))
    
    # If the name is empty after sanitization, use a default
    if not sanitized:
        return "user"
    
    return sanitized

def store_message(server, guild_id, channel_id, role, name, content):
    """Store a message in the server's chat history and database."""
    # Store in database
    db.store_message(guild_id, channel_id, role, sanitize_name(name) if role == "user" else None, content)
    
    # Initialize channel history in cache if it doesn't exist
    if 'chat_history' not in server:
        server['chat_history'] = {}
    
    if channel_id not in server['chat_history']:
        server['chat_history'][channel_id] = []
    
    # Add message to cached history
    server['chat_history'][channel_id].append({
        "role": role,
        "name": sanitize_name(name) if role == "user" else None,
        "content": content
    })
    
    # Limit cached history size
    if len(server['chat_history'][channel_id]) > MESSAGE_HISTORY_LIMIT * 2:  # Store twice as many as we use
        server['chat_history'][channel_id] = server['chat_history'][channel_id][-MESSAGE_HISTORY_LIMIT * 2:]

async def get_message_history(channel, current_message, limit, server):
    """Get the message history from the server's stored chat history or database."""
    guild_id = channel.guild.id
    channel_id = channel.id
    
    # If we have cached history for this channel, use it
    if 'chat_history' in server and channel_id in server['chat_history']:
        return server['chat_history'][channel_id][-limit:]
    
    # Otherwise, fetch from database
    db_messages = db.get_message_history(guild_id, channel_id, limit)
    
    # If we have history in the database, use it
    if db_messages:
        # Cache the messages
        if 'chat_history' not in server:
            server['chat_history'] = {}
        server['chat_history'][channel_id] = db_messages
        return db_messages
    
    # If no history in database, fetch from Discord and initialize history
    messages = []
    try:
        async for msg in channel.history(limit=limit, before=current_message):
            # Determine the role based on whether the message is from the bot
            role = "assistant" if msg.author == bot.user else "user"
            
            message_data = {
                "role": role,
                "content": msg.content
            }
            
            # Only include name for user messages, and ensure it's properly sanitized
            if role == "user":
                message_data["name"] = sanitize_name(msg.author.display_name)
            
            messages.append(message_data)
            
            # Store in database and server's chat history
            store_message(server, guild_id, channel_id, role, msg.author.display_name, msg.content)
    except Exception as e:
        print(f"Error getting message history: {e}")
    
    # Reverse the messages to get them in chronological order
    messages.reverse()
    return messages

async def generate_response(prompt, message_history, persona_key):
    """Generate a response using OpenAI's API with message history context."""
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Get the persona's system prompt
        persona_info = personas.get(persona_key, personas[default_persona])
        system_prompt = persona_info["system_prompt"]
        
        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add message history for context
        if message_history:
            messages.extend(message_history)
        
        # Add the current prompt with sanitized name
        messages.append({
            "role": "user", 
            "name": sanitize_name(f"user_{len(messages)}"),
            "content": prompt
        })
        
        # For debugging
        print(f"Using persona: {persona_key}")
        print(f"Sending {len(messages)} messages to OpenAI")
        
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
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Run the bot
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
    finally:
        # Close database connection when bot exits
        db.close()

if __name__ == "__main__":
    main()
