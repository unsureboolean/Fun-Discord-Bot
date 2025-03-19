"""
Logging module for monitoring and debugging.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import datetime

class BotLogger:
    """Logger class for the Discord bot."""
    
    def __init__(self, log_dir="logs", log_level=logging.INFO):
        """
        Initialize the logger.
        
        Args:
            log_dir: Directory to store log files
            log_level: Logging level (default: INFO)
        """
        # Create logs directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger("discord_bot")
        self.logger.setLevel(log_level)
        
        # Remove existing handlers if any
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler for general logs
        general_log_file = os.path.join(log_dir, "bot.log")
        file_handler = RotatingFileHandler(
            general_log_file, maxBytes=10485760, backupCount=5
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Create file handler for error logs
        error_log_file = os.path.join(log_dir, "error.log")
        error_handler = RotatingFileHandler(
            error_log_file, maxBytes=10485760, backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
        
        # Create file handler for API calls
        api_log_file = os.path.join(log_dir, "api.log")
        self.api_handler = RotatingFileHandler(
            api_log_file, maxBytes=10485760, backupCount=5
        )
        self.api_handler.setFormatter(formatter)
        self.api_logger = logging.getLogger("discord_bot.api")
        self.api_logger.setLevel(logging.INFO)
        self.api_logger.addHandler(self.api_handler)
        
        # Create file handler for command usage
        command_log_file = os.path.join(log_dir, "commands.log")
        self.command_handler = RotatingFileHandler(
            command_log_file, maxBytes=10485760, backupCount=5
        )
        self.command_handler.setFormatter(formatter)
        self.command_logger = logging.getLogger("discord_bot.commands")
        self.command_logger.setLevel(logging.INFO)
        self.command_logger.addHandler(self.command_handler)
    
    def info(self, message):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message, exc_info=None):
        """Log an error message."""
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message, exc_info=None):
        """Log a critical message."""
        self.logger.critical(message, exc_info=exc_info)
    
    def debug(self, message):
        """Log a debug message."""
        self.logger.debug(message)
    
    def log_api_call(self, api_name, params=None, success=True, response=None, error=None):
        """
        Log an API call.
        
        Args:
            api_name: Name of the API being called
            params: Parameters passed to the API (optional)
            success: Whether the call was successful
            response: API response (optional)
            error: Error message if the call failed (optional)
        """
        log_message = f"API Call: {api_name}"
        
        if params:
            # Sanitize parameters to remove sensitive information
            sanitized_params = self._sanitize_params(params)
            log_message += f", Params: {sanitized_params}"
        
        if success:
            log_message += ", Status: Success"
            if response:
                # Truncate response if too long
                response_str = str(response)
                if len(response_str) > 500:
                    response_str = response_str[:500] + "..."
                log_message += f", Response: {response_str}"
        else:
            log_message += f", Status: Failed, Error: {error}"
        
        self.api_logger.info(log_message)
    
    def log_command(self, command_name, user_id, guild_id, channel_id, success=True, error=None):
        """
        Log a command execution.
        
        Args:
            command_name: Name of the command
            user_id: ID of the user who executed the command
            guild_id: ID of the guild where the command was executed
            channel_id: ID of the channel where the command was executed
            success: Whether the command execution was successful
            error: Error message if the command failed (optional)
        """
        log_message = f"Command: {command_name}, User: {user_id}, Guild: {guild_id}, Channel: {channel_id}"
        
        if success:
            log_message += ", Status: Success"
        else:
            log_message += f", Status: Failed, Error: {error}"
        
        self.command_logger.info(log_message)
    
    def log_rate_limit(self, user_id, guild_id, command_name, reason, retry_after):
        """
        Log a rate limit event.
        
        Args:
            user_id: ID of the rate-limited user
            guild_id: ID of the guild
            command_name: Name of the command (if applicable)
            reason: Reason for rate limiting
            retry_after: Seconds until the rate limit expires
        """
        log_message = f"Rate Limit: User: {user_id}, Guild: {guild_id}"
        
        if command_name:
            log_message += f", Command: {command_name}"
        
        log_message += f", Reason: {reason}, Retry After: {retry_after}s"
        
        self.warning(log_message)
    
    def _sanitize_params(self, params):
        """
        Sanitize parameters to remove sensitive information.
        
        Args:
            params: Parameters to sanitize
            
        Returns:
            dict: Sanitized parameters
        """
        if not isinstance(params, dict):
            return params
        
        sanitized = params.copy()
        
        # List of sensitive parameter names
        sensitive_params = ["api_key", "token", "password", "secret"]
        
        # Replace sensitive values with asterisks
        for key in sanitized:
            if any(sensitive in key.lower() for sensitive in sensitive_params):
                sanitized[key] = "********"
        
        return sanitized
