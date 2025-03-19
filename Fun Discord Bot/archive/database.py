import sqlite3
import json
import os

class Database:
    """Database class for persistent storage."""
    
    def __init__(self, db_path):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect to database
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Create tables if they don't exist
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Create servers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            guild_id TEXT PRIMARY KEY,
            persona TEXT NOT NULL,
            settings TEXT
        )
        ''')
        
        # Create messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL,
            name TEXT,
            content TEXT NOT NULL
        )
        ''')
        
        # Create settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        ''')
        
        self.conn.commit()
    
    def get_server_data(self, guild_id, default_persona):
        """
        Get server-specific data.
        
        Args:
            guild_id: Discord guild ID
            default_persona: Default persona to use if not set
            
        Returns:
            dict: Server data
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM servers WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        
        if row:
            # Convert settings from JSON
            settings = json.loads(row['settings']) if row['settings'] else {}
            
            return {
                'guild_id': row['guild_id'],
                'persona': row['persona'],
                **settings
            }
        else:
            # Initialize new server with default persona
            cursor.execute(
                'INSERT INTO servers (guild_id, persona, settings) VALUES (?, ?, ?)',
                (guild_id, default_persona, '{}')
            )
            self.conn.commit()
            
            return {
                'guild_id': guild_id,
                'persona': default_persona
            }
    
    def update_server_persona(self, guild_id, persona):
        """
        Update a server's active persona.
        
        Args:
            guild_id: Discord guild ID
            persona: Persona key to set
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE servers SET persona = ? WHERE guild_id = ?',
            (persona, guild_id)
        )
        
        # If no rows were updated, insert a new row
        if cursor.rowcount == 0:
            cursor.execute(
                'INSERT INTO servers (guild_id, persona, settings) VALUES (?, ?, ?)',
                (guild_id, persona, '{}')
            )
        
        self.conn.commit()
        
    def update_user_max_sentences(self, guild_id, user_id, max_sentences):
        """
        Update a user's maximum sentences preference.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            max_sentences: Maximum number of sentences in responses
        """
        cursor = self.conn.cursor()
        
        # Get current server settings
        cursor.execute('SELECT settings FROM servers WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        
        if row:
            # Parse existing settings
            settings = json.loads(row['settings']) if row['settings'] else {}
            
            # Initialize user_preferences if it doesn't exist
            if 'user_preferences' not in settings:
                settings['user_preferences'] = {}
                
            # Update max_sentences for this user
            if 'users' not in settings['user_preferences']:
                settings['user_preferences']['users'] = {}
                
            settings['user_preferences']['users'][str(user_id)] = {
                'max_sentences': max_sentences
            }
            
            # Save updated settings
            cursor.execute(
                'UPDATE servers SET settings = ? WHERE guild_id = ?',
                (json.dumps(settings), guild_id)
            )
            self.conn.commit()
            return True
        return False
        
    def get_user_max_sentences(self, guild_id, user_id, default_max_sentences):
        """
        Get a user's maximum sentences preference.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            default_max_sentences: Default value if not set
            
        Returns:
            int: Maximum number of sentences for responses
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT settings FROM servers WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        
        if row and row['settings']:
            settings = json.loads(row['settings'])
            
            # Check if user has a preference
            if ('user_preferences' in settings and 
                'users' in settings['user_preferences'] and 
                str(user_id) in settings['user_preferences']['users'] and
                'max_sentences' in settings['user_preferences']['users'][str(user_id)]):
                return settings['user_preferences']['users'][str(user_id)]['max_sentences']
        
        # Return default if no preference is set
        return default_max_sentences
    
    def store_message(self, guild_id, channel_id, role, name, content):
        """
        Store a message in the database.
        
        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID
            role: Message role (user or assistant)
            name: Username (only for user messages)
            content: Message content
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO messages (guild_id, channel_id, role, name, content) VALUES (?, ?, ?, ?, ?)',
            (guild_id, channel_id, role, name, content)
        )
        self.conn.commit()
    
    def get_message_history(self, guild_id, channel_id, limit):
        """
        Get message history for a channel.
        
        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            list: List of message dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            SELECT role, name, content FROM messages 
            WHERE guild_id = ? AND channel_id = ? 
            ORDER BY timestamp ASC
            LIMIT ?
            ''',
            (guild_id, channel_id, limit)
        )
        
        messages = []
        for row in cursor.fetchall():
            message = {
                'role': row['role'],
                'content': row['content']
            }
            
            # Only include name for user messages
            if row['role'] == 'user' and row['name']:
                message['name'] = row['name']
            
            messages.append(message)
        
        return messages
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
