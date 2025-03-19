# Discord OpenAI Bot - Enhanced Edition  

A feature-packed Discord bot designed for private servers, offering AI-powered interactions, multiple personas, and a range of fun and engaging commands. Built for entertainment and moderation, the bot includes:  

## Core Features  

- **Multiple AI Personas** – Switch between 9 different personalities, from a helpful assistant to pop culture icons like Jack Sparrow and Homer Simpson.  
- **Persistent Chat History** – The bot remembers past conversations using SQLite, maintaining context even after restarts.  

### Advanced Slash Commands  
- `/persona` – Change the bot’s personality *(mod/admin only)*  
- `/generate_image` – Create AI-generated images with OpenAI’s DALL-E *(admin only)*  
- `/insult` – Playfully roast a user with expanded, persona-based insults *(mod/admin only)*  
- `/purge` – Bulk delete messages for easier moderation *(mod only)*  
- `/warn` – Issue a warning to a user *(mod only)*  

### Role-Based Permissions  
Commands are restricted based on user roles, ensuring controlled access.  

### Rate Limiting  
Prevents abuse with user, server, and command-specific limits.  

### Comprehensive Logging  
Tracks commands, errors, and bot activity for debugging.  

### Flexible Deployment  
Run locally or deploy with Docker for easy setup.  

---

Whether you're looking for an AI-powered conversationalist, a meme-worthy insult bot, or a light moderation tool, this bot delivers a fun and dynamic experience tailored to your private Discord server.  
