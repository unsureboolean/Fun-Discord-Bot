# Enhanced Discord OpenAI Bot

This Discord bot utilizes the OpenAI API to chat with users when tagged in a message. It includes several advanced features such as moderation tools, a reminder system, and customizable response lengths.

## Features

### Core Functionality
- AI-powered chat responses using OpenAI's GPT models
- Customizable AI personas
- Message history tracking for context-aware conversations
- Rate limiting to prevent API abuse

### Moderation Tools
- `/purge [number]` - Deletes a specified number of messages (moderators only)
- `/warn [user] [reason]` - Issues a warning to a user
- `/insult [user]` - Tags and insults a specific user or a random user (moderators only)

### User Preferences
- `/set_response_length [sentences]` - Set the maximum number of sentences in bot responses (0-10, where 0 means unlimited)

### Reminder System
- `/remindme [time] [message]` - The bot pings the user after a set time

## Installation

1. Clone this repository
2. Install the required packages:
```
pip install -r requirements.txt
```
3. Create a `.env` file in the root directory with the following variables:
```
DISCORD_TOKEN=your_discord_token_here
DISCORD_APPLICATION_ID=your_application_id_here
OPENAI_API_KEY=your_openai_api_key_here
```
4. Run the bot:
```
python src/bot.py
```

## Requirements

- Python 3.10 or higher
- discord.py 2.0.0 or higher
- openai 1.0.0 or higher
- python-dotenv
- nltk

## File Structure

- `src/` - Contains the main bot code
  - `bot.py` - Main bot file
  - `database.py` - Database handling
  - `logger.py` - Logging functionality
  - `permissions.py` - Permission management
  - `personas.py` - AI personas configuration
  - `rate_limiting.py` - Rate limiting functionality
- `archive/` - Contains previous versions of the bot

## Troubleshooting

### NLTK Resource Error
If you encounter an error related to NLTK resources, run the following Python code to download the required data:
```python
import nltk
nltk.download('punkt')
```

### Database Errors
The bot automatically creates necessary directories and database files. If you encounter database errors, ensure the bot has write permissions to the directory.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
