import os
import discord
from discord.ext import commands
from discord import app_commands
import openai
import re
import json
import random
import nltk
from dotenv import load_dotenv
from personas import personas, default_persona
from database import Database
from permissions import PermissionLevel, check_permission
from logger import BotLogger
from rate_limiting import RateLimitType, rate_limiter, format_time_remaining

# Download nltk data for sentence tokenization
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Load environment variables
load_dotenv()

# Configure Discord bot
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
BOT_NAME = os.getenv('BOT_NAME', 'General Brasch')
MESSAGE_HISTORY_LIMIT = int(os.getenv('MESSAGE_HISTORY_LIMIT', 10))
DEFAULT_MAX_SENTENCES = int(os.getenv('DEFAULT_MAX_SENTENCES', 5))  # Default max sentences in responses

# Configure OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set up Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
intents.members = True  # Enable members intent
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

# Initialize database
db = Database("data/bot_data.db")

# Initialize logger
logger = BotLogger(log_dir="logs")

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
    logger.info(f'{bot.user.name} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info(f'Bot Application ID: {DISCORD_APPLICATION_ID}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)

@bot.tree.command(name="persona", description="Change the bot's persona (Moderators and Admins only)")
@app_commands.describe(persona_choice="Choose the bot's persona")
@app_commands.choices(persona_choice=[
    app_commands.Choice(name=persona_info["name"], value=persona_key)
    for persona_key, persona_info in personas.items()
])
async def change_persona(interaction: discord.Interaction, persona_choice: str):
    """Slash command to change the bot's persona (restricted to moderators and admins)."""
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        logger.log_command("persona", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Command used in DM")
        return
    
    # Check if user has permission to change persona
    if not check_permission(interaction, PermissionLevel.MODERATOR):
        await interaction.response.send_message(
            "You don't have permission to change the bot's persona. This command is restricted to moderators and admins.",
            ephemeral=True
        )
        logger.log_command("persona", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Insufficient permissions")
        return
    
    # Check rate limits
    is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(
        RateLimitType.COMMAND, interaction.user.id, interaction.guild_id
    )
    
    if is_limited:
        await interaction.response.send_message(
            f"You're changing personas too quickly. Please wait {format_time_remaining(wait_time)} before trying again.",
            ephemeral=True
        )
        logger.log_rate_limit(interaction.user.id, interaction.guild_id, "persona", 
                             "Command rate limit exceeded", wait_time)
        return
    
    # Record the request for rate limiting
    rate_limiter.add_request(RateLimitType.COMMAND, interaction.user.id, interaction.guild_id)
    
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
            logger.log_command("persona", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                              success=True)
            logger.info(f"Persona changed to {persona_choice} in guild {interaction.guild_id} by user {interaction.user.id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Persona changed to '{personas[persona_choice]['name']}', but I don't have permission to change my nickname.",
                ephemeral=True
            )
            logger.log_command("persona", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                              success=True)
            logger.warning(f"Persona changed but couldn't update nickname in guild {interaction.guild_id}")
    else:
        await interaction.response.send_message(f"Unknown persona: {persona_choice}", ephemeral=True)
        logger.log_command("persona", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error=f"Unknown persona: {persona_choice}")

@bot.tree.command(name="generate_image", description="Generate an image using OpenAI (Admins only)")
@app_commands.describe(prompt="Description of the image to generate")
async def generate_image(interaction: discord.Interaction, prompt: str):
    """Slash command to generate an image using OpenAI's API (restricted to admins)."""
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        logger.log_command("generate_image", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Command used in DM")
        return
    
    # Check if user has permission to generate images
    if not check_permission(interaction, PermissionLevel.ADMIN):
        await interaction.response.send_message(
            "You don't have permission to generate images. This command is restricted to server admins.",
            ephemeral=True
        )
        logger.log_command("generate_image", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Insufficient permissions")
        return
    
    # Check rate limits
    is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(
        RateLimitType.IMAGE, interaction.user.id, interaction.guild_id
    )
    
    if is_limited:
        await interaction.response.send_message(
            f"You're generating images too quickly. Please wait {format_time_remaining(wait_time)} before trying again.",
            ephemeral=True
        )
        logger.log_rate_limit(interaction.user.id, interaction.guild_id, "generate_image", 
                             "Image generation rate limit exceeded", wait_time)
        return
    
    # Defer response since image generation might take time
    await interaction.response.defer(thinking=True)
    
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Log API call
        logger.log_api_call("OpenAI Image Generation", {"prompt": prompt})
        
        # Generate image
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        # Record the request for rate limiting
        rate_limiter.add_request(RateLimitType.IMAGE, interaction.user.id, interaction.guild_id)
        
        # Get image URL
        image_url = response.data[0].url
        
        # Create embed with the image
        embed = discord.Embed(title="Generated Image", description=f"Prompt: {prompt}")
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")
        
        # Send the image
        await interaction.followup.send(embed=embed)
        logger.log_command("generate_image", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=True)
        logger.info(f"Image generated in guild {interaction.guild_id} by user {interaction.user.id}")
    except Exception as e:
        error_msg = f"Error generating image: {str(e)}"
        logger.error(error_msg, exc_info=True)
        logger.log_command("generate_image", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error=str(e))
        await interaction.followup.send("I'm sorry, I encountered an error while generating the image.")

@bot.tree.command(name="set_response_length", description="Set the maximum number of sentences in bot responses")
@app_commands.describe(sentences="Number of sentences (1-10, or 0 for unlimited)")
async def set_response_length(interaction: discord.Interaction, sentences: int):
    """Slash command to set the maximum number of sentences in bot responses."""
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        logger.log_command("set_response_length", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Command used in DM")
        return
    
    # Validate input
    if sentences < 0 or sentences > 10:
        await interaction.response.send_message(
            "Please provide a number between 0 and 10. Use 0 for unlimited sentences.",
            ephemeral=True
        )
        logger.log_command("set_response_length", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Invalid sentence count")
        return
    
    # Check rate limits
    is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(
        RateLimitType.COMMAND, interaction.user.id, interaction.guild_id
    )
    
    if is_limited:
        await interaction.response.send_message(
            f"You're changing settings too quickly. Please wait {format_time_remaining(wait_time)} before trying again.",
            ephemeral=True
        )
        logger.log_rate_limit(interaction.user.id, interaction.guild_id, "set_response_length", 
                             "Command rate limit exceeded", wait_time)
        return
    
    # Record the request for rate limiting
    rate_limiter.add_request(RateLimitType.COMMAND, interaction.user.id, interaction.guild_id)
    
    # Update user's preference in database
    success = db.update_user_max_sentences(interaction.guild_id, interaction.user.id, sentences)
    
    if success:
        # Prepare response message
        if sentences == 0:
            message = "Response length set to unlimited. The bot will now provide full responses."
        else:
            message = f"Response length set to {sentences} sentence{'s' if sentences != 1 else ''}. The bot will now limit its responses accordingly."
        
        await interaction.response.send_message(message, ephemeral=True)
        logger.log_command("set_response_length", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=True)
        logger.info(f"Response length set to {sentences} for user {interaction.user.id} in guild {interaction.guild_id}")
    else:
        await interaction.response.send_message(
            "I encountered an error while updating your preference. Please try again later.",
            ephemeral=True
        )
        logger.log_command("set_response_length", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Database update failed")

@bot.tree.command(name="insult", description="Tag and insult a random user in the channel (Moderators and Admins only)")
async def insult_random_user(interaction: discord.Interaction):
    """Slash command to tag and insult a random user in the channel (restricted to moderators and admins)."""
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        logger.log_command("insult", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Command used in DM")
        return
    
    # Check if user has permission to use this command
    if not check_permission(interaction, PermissionLevel.MODERATOR):
        await interaction.response.send_message(
            "You don't have permission to use this command. This command is restricted to moderators and admins.",
            ephemeral=True
        )
        logger.log_command("insult", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error="Insufficient permissions")
        return
    
    # Check rate limits
    is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(
        RateLimitType.INSULT, interaction.user.id, interaction.guild_id
    )
    
    if is_limited:
        await interaction.response.send_message(
            f"You're using the insult command too quickly. Please wait {format_time_remaining(wait_time)} before trying again.",
            ephemeral=True
        )
        logger.log_rate_limit(interaction.user.id, interaction.guild_id, "insult", 
                             "Insult command rate limit exceeded", wait_time)
        return
    
    # Defer response since we'll need to generate content
    await interaction.response.defer(thinking=True)
    
    try:
        # Get server data for current persona
        server = get_server_data(interaction.guild_id)
        persona_key = server['persona']
        
        # Get all members in the channel
        channel_members = [
            member for member in interaction.channel.members
            if not member.bot and member.id != interaction.user.id
        ]
        
        if not channel_members:
            await interaction.followup.send("There are no other users in this channel to insult.")
            logger.log_command("insult", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                              success=False, error="No valid targets in channel")
            return
        
        # Select a random member
        target_member = random.choice(channel_members)
        
        # Generate insult using current persona
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Get the persona's system prompt
        persona_info = personas.get(persona_key, personas[default_persona])
        system_prompt = persona_info["system_prompt"]
        
        # Create a prompt for the insult
        insult_prompt = f"Create a humorous, light-hearted insult directed at {target_member.display_name}. The insult should be playful, not genuinely mean or offensive. Keep it appropriate for a Discord server."
        
        # Log API call
        logger.log_api_call("OpenAI Chat Completion", {
            "persona": persona_key,
            "target_user": target_member.display_name
        })
        
        # Generate the insult
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": insult_prompt}
            ],
            max_tokens=150,
            temperature=0.8
        )
        
        # Record the request for rate limiting
        rate_limiter.add_request(RateLimitType.INSULT, interaction.user.id, interaction.guild_id)
        
        # Extract the insult
        insult = response.choices[0].message.content
        
        # Send the insult, tagging the target user
        await interaction.followup.send(f"<@{target_member.id}> {insult}")
        logger.log_command("insult", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=True)
        logger.info(f"Insult generated for user {target_member.id} in guild {interaction.guild_id}")
    except Exception as e:
        error_msg = f"Error generating insult: {str(e)}"
        logger.error(error_msg, exc_info=True)
        logger.log_command("insult", interaction.user.id, interaction.guild_id, interaction.channel_id, 
                          success=False, error=str(e))
        await interaction.followup.send("I'm sorry, I encountered an error while trying to insult someone.")

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
            # Check rate limits
            is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(
                RateLimitType.MESSAGE, message.author.id, message.guild.id
            )
            
            if is_limited:
                await message.reply(
                    f"You're sending messages too quickly. Please wait {format_time_remaining(wait_time)} before trying again."
                )
                logger.log_rate_limit(message.author.id, message.guild.id, "message", 
                                     "Message rate limit exceeded", wait_time)
                return
            
            try:
                # Get server data
                server = get_server_data(message.guild.id)
                
                # Get message history for context
                message_history = await get_message_history(message.channel, message, MESSAGE_HISTORY_LIMIT, server)
                
                # Log API call
                logger.log_api_call("OpenAI Chat Completion", {
                    "persona": server['persona'],
                    "message_history_length": len(message_history)
                })
                
                # Generate response with context
                response = await generate_response(content, message_history, server['persona'], 
                                                 user_id=message.author.id, guild_id=message.guild.id)
                
                # Record the request for rate limiting
                rate_limiter.add_request(RateLimitType.MESSAGE, message.author.id, message.guild.id)
                
                # Store the interaction in chat history
                store_message(server, message.guild.id, message.channel.id, "user", message.author.display_name, content)
                store_message(server, message.guild.id, message.channel.id, "assistant", bot.user.display_name, response)
                
                # Send the response
                await message.reply(response)
                logger.info(f"Responded to message from {message.author.id} in guild {message.guild.id}")
            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                logger.error(error_msg, exc_info=True)
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
        logger.error(f"Error getting message history: {e}", exc_info=True)
    
    # Reverse the messages to get them in chronological order
    messages.reverse()
    return messages

async def generate_response(prompt, message_history, persona_key, user_id=None, guild_id=None):
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
        logger.debug(f"Using persona: {persona_key}")
        logger.debug(f"Sending {len(messages)} messages to OpenAI")
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You can change this to a different model
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content
        
        # Apply sentence limiting if user_id and guild_id are provided
        if user_id and guild_id:
            # Get user's max sentences preference
            max_sentences = db.get_user_max_sentences(guild_id, user_id, DEFAULT_MAX_SENTENCES)
            
            # Limit sentences if max_sentences is set
            if max_sentences > 0:
                # Use NLTK to split into sentences
                sentences = nltk.sent_tokenize(response_text)
                
                # Limit to max_sentences
                if len(sentences) > max_sentences:
                    limited_response = ' '.join(sentences[:max_sentences])
                    logger.debug(f"Limited response from {len(sentences)} to {max_sentences} sentences for user {user_id}")
                    return limited_response
        
        # Return the full response if no limiting was applied
        return response_text
    except Exception as e:
        logger.error(f"OpenAI API error: {e}", exc_info=True)
        raise

def main():
    """Main function to run the bot."""
    try:
        # Ensure data and logs directories exist
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        logger.info("Starting Discord bot")
        
        # Run the bot
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Error running bot: {e}", exc_info=True)
    finally:
        # Close database connection when bot exits
        db.close()
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    main()
