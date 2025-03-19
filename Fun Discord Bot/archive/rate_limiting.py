"""
Rate limiting and logging module for the Discord bot.
"""
import time
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data/bot.log"),
        logging.StreamHandler()
    ]
)

# Create logger
logger = logging.getLogger('discord_bot')

class RateLimitType(Enum):
    """Enum for rate limit types."""
    MESSAGE = "message"
    COMMAND = "command"
    IMAGE = "image"
    INSULT = "insult"

class RateLimiter:
    """Rate limiter class to prevent API abuse."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        # Structure: {rate_limit_type: {user_id: [timestamp1, timestamp2, ...]}}
        self.user_requests = defaultdict(lambda: defaultdict(list))
        
        # Default rate limits
        self.rate_limits = {
            RateLimitType.MESSAGE: (10, 60),  # 10 messages per 60 seconds
            RateLimitType.COMMAND: (5, 60),   # 5 commands per 60 seconds
            RateLimitType.IMAGE: (3, 300),    # 3 image generations per 300 seconds (5 minutes)
            RateLimitType.INSULT: (2, 300),   # 2 insults per 300 seconds (5 minutes)
        }
        
        # Server-wide rate limits
        self.server_requests = defaultdict(list)
        self.server_rate_limits = {
            RateLimitType.MESSAGE: (30, 60),  # 30 messages per 60 seconds per server
            RateLimitType.IMAGE: (10, 600),   # 10 images per 600 seconds (10 minutes) per server
        }
        
        logger.info("Rate limiter initialized with default limits")
    
    def _clean_old_timestamps(self, timestamps, window_seconds):
        """Remove timestamps older than the window."""
        cutoff_time = time.time() - window_seconds
        return [ts for ts in timestamps if ts > cutoff_time]
    
    def is_rate_limited(self, rate_limit_type, user_id, guild_id=None):
        """
        Check if a user is rate limited for a specific action.
        
        Args:
            rate_limit_type: Type of rate limit to check
            user_id: Discord user ID
            guild_id: Discord guild ID (optional, for server-wide limits)
            
        Returns:
            tuple: (is_limited, wait_time, limit_info)
        """
        # Get rate limit configuration
        max_requests, window_seconds = self.rate_limits[rate_limit_type]
        
        # Clean old timestamps for user
        self.user_requests[rate_limit_type][user_id] = self._clean_old_timestamps(
            self.user_requests[rate_limit_type][user_id], window_seconds
        )
        
        # Check user rate limit
        user_timestamps = self.user_requests[rate_limit_type][user_id]
        if len(user_timestamps) >= max_requests:
            oldest_timestamp = min(user_timestamps)
            reset_time = oldest_timestamp + window_seconds
            wait_time = reset_time - time.time()
            
            logger.warning(
                f"Rate limit exceeded for user {user_id} on {rate_limit_type.value}. "
                f"Limit: {max_requests} per {window_seconds}s. "
                f"Wait time: {wait_time:.1f}s"
            )
            
            return True, wait_time, f"{max_requests} per {window_seconds}s"
        
        # Check server-wide rate limit if guild_id is provided
        if guild_id and rate_limit_type in self.server_rate_limits:
            server_max, server_window = self.server_rate_limits[rate_limit_type]
            
            # Clean old timestamps for server
            self.server_requests[f"{rate_limit_type.value}_{guild_id}"] = self._clean_old_timestamps(
                self.server_requests[f"{rate_limit_type.value}_{guild_id}"], server_window
            )
            
            server_timestamps = self.server_requests[f"{rate_limit_type.value}_{guild_id}"]
            if len(server_timestamps) >= server_max:
                oldest_timestamp = min(server_timestamps)
                reset_time = oldest_timestamp + server_window
                wait_time = reset_time - time.time()
                
                logger.warning(
                    f"Server rate limit exceeded for guild {guild_id} on {rate_limit_type.value}. "
                    f"Limit: {server_max} per {server_window}s. "
                    f"Wait time: {wait_time:.1f}s"
                )
                
                return True, wait_time, f"{server_max} per {server_window}s (server-wide)"
        
        return False, 0, None
    
    def add_request(self, rate_limit_type, user_id, guild_id=None):
        """
        Record a request for rate limiting purposes.
        
        Args:
            rate_limit_type: Type of rate limit
            user_id: Discord user ID
            guild_id: Discord guild ID (optional, for server-wide limits)
        """
        current_time = time.time()
        
        # Add timestamp for user
        self.user_requests[rate_limit_type][user_id].append(current_time)
        
        # Add timestamp for server if guild_id is provided
        if guild_id:
            self.server_requests[f"{rate_limit_type.value}_{guild_id}"].append(current_time)
        
        logger.debug(
            f"Request recorded: type={rate_limit_type.value}, user={user_id}, "
            f"guild={guild_id if guild_id else 'N/A'}"
        )
    
    def get_remaining_requests(self, rate_limit_type, user_id):
        """
        Get the number of remaining requests for a user.
        
        Args:
            rate_limit_type: Type of rate limit
            user_id: Discord user ID
            
        Returns:
            tuple: (remaining_requests, reset_time)
        """
        max_requests, window_seconds = self.rate_limits[rate_limit_type]
        
        # Clean old timestamps
        self.user_requests[rate_limit_type][user_id] = self._clean_old_timestamps(
            self.user_requests[rate_limit_type][user_id], window_seconds
        )
        
        # Calculate remaining requests
        current_requests = len(self.user_requests[rate_limit_type][user_id])
        remaining = max(0, max_requests - current_requests)
        
        # Calculate reset time
        if current_requests > 0:
            oldest_timestamp = min(self.user_requests[rate_limit_type][user_id])
            reset_time = oldest_timestamp + window_seconds
        else:
            reset_time = time.time() + window_seconds
        
        return remaining, reset_time
    
    def update_rate_limit(self, rate_limit_type, max_requests, window_seconds):
        """
        Update a rate limit configuration.
        
        Args:
            rate_limit_type: Type of rate limit to update
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds
        """
        self.rate_limits[rate_limit_type] = (max_requests, window_seconds)
        logger.info(
            f"Rate limit updated for {rate_limit_type.value}: "
            f"{max_requests} requests per {window_seconds} seconds"
        )

# Create a global rate limiter instance
rate_limiter = RateLimiter()

def format_time_remaining(seconds):
    """Format seconds into a human-readable time string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} minutes"
    else:
        return f"{seconds / 3600:.1f} hours"

def log_command(command_name, user_id, user_name, guild_id, guild_name, success=True, error=None):
    """Log a command execution."""
    status = "SUCCESS" if success else "FAILED"
    error_msg = f" - Error: {error}" if error else ""
    
    logger.info(
        f"COMMAND {status}: {command_name} - User: {user_name} ({user_id}) - "
        f"Server: {guild_name} ({guild_id}){error_msg}"
    )

def log_api_call(api_name, params, success=True, error=None, response=None):
    """Log an API call."""
    status = "SUCCESS" if success else "FAILED"
    error_msg = f" - Error: {error}" if error else ""
    response_summary = f" - Response: {str(response)[:100]}..." if response and success else ""
    
    logger.info(
        f"API {status}: {api_name} - Params: {str(params)[:100]}...{error_msg}{response_summary}"
    )

def log_message(message_type, user_id, user_name, guild_id, guild_name, channel_id, content=None):
    """Log a message event."""
    content_summary = f" - Content: {content[:50]}..." if content else ""
    
    logger.debug(
        f"MESSAGE {message_type}: User: {user_name} ({user_id}) - "
        f"Server: {guild_name} ({guild_id}) - Channel: {channel_id}{content_summary}"
    )

def log_error(error_type, error_message, user_id=None, guild_id=None):
    """Log an error."""
    user_info = f" - User: {user_id}" if user_id else ""
    guild_info = f" - Server: {guild_id}" if guild_id else ""
    
    logger.error(
        f"ERROR {error_type}: {error_message}{user_info}{guild_info}"
    )

def setup_logging(log_level=logging.INFO):
    """Set up logging with the specified log level."""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Configure file handler with rotation
    file_handler = logging.FileHandler("data/bot.log")
    file_handler.setLevel(log_level)
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Get the logger and add handlers
    logger = logging.getLogger('discord_bot')
    logger.setLevel(log_level)
    
    # Remove existing handlers if any
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info("Logging system initialized")
    return logger
