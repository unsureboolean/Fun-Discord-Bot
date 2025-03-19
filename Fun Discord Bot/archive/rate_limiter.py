"""
Rate limiting module for preventing API abuse.
"""
import time
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    """Rate limiter class to prevent API abuse."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        # Store user request counts: {user_id: [(timestamp, count), ...]}
        self.user_requests = defaultdict(list)
        
        # Store guild request counts: {guild_id: [(timestamp, count), ...]}
        self.guild_requests = defaultdict(list)
        
        # Store global request counts: [(timestamp, count), ...]
        self.global_requests = []
        
        # Default rate limits
        self.user_rate_limit = 10  # requests per user per minute
        self.guild_rate_limit = 30  # requests per guild per minute
        self.global_rate_limit = 100  # total requests per minute
        
        # Command-specific rate limits: {command_name: limit_per_minute}
        self.command_rate_limits = {
            "generate_image": 5,  # 5 image generations per minute globally
            "insult": 3  # 3 insults per minute per guild
        }
        
        # Command request counts: {command_name: [(timestamp, count), ...]}
        self.command_requests = defaultdict(list)
    
    def _clean_old_requests(self, request_list, window_seconds=60):
        """Remove requests older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Keep only requests within the time window
        return [req for req in request_list if req[0] >= cutoff_time]
    
    def _count_requests(self, request_list, window_seconds=60):
        """Count requests within the time window."""
        # Clean old requests first
        cleaned_list = self._clean_old_requests(request_list, window_seconds)
        
        # Sum the counts
        return sum(count for _, count in cleaned_list)
    
    def check_rate_limit(self, user_id, guild_id, command_name=None):
        """
        Check if a request exceeds rate limits.
        
        Args:
            user_id: The user's ID
            guild_id: The guild's ID
            command_name: Optional command name for command-specific limits
            
        Returns:
            tuple: (is_rate_limited, reason, retry_after_seconds)
        """
        current_time = time.time()
        
        # Clean and update user requests
        self.user_requests[user_id] = self._clean_old_requests(self.user_requests[user_id])
        user_count = self._count_requests(self.user_requests[user_id])
        
        # Clean and update guild requests
        self.guild_requests[guild_id] = self._clean_old_requests(self.guild_requests[guild_id])
        guild_count = self._count_requests(self.guild_requests[guild_id])
        
        # Clean and update global requests
        self.global_requests = self._clean_old_requests(self.global_requests)
        global_count = self._count_requests(self.global_requests)
        
        # Check command-specific rate limits if applicable
        if command_name and command_name in self.command_rate_limits:
            self.command_requests[command_name] = self._clean_old_requests(self.command_requests[command_name])
            command_count = self._count_requests(self.command_requests[command_name])
            command_limit = self.command_rate_limits[command_name]
            
            if command_count >= command_limit:
                # Calculate retry after time
                oldest_timestamp = min([req[0] for req in self.command_requests[command_name]]) if self.command_requests[command_name] else current_time
                retry_after = max(0, 60 - (current_time - oldest_timestamp))
                return True, f"Command rate limit exceeded for {command_name}", retry_after
        
        # Check user rate limit
        if user_count >= self.user_rate_limit:
            oldest_timestamp = min([req[0] for req in self.user_requests[user_id]]) if self.user_requests[user_id] else current_time
            retry_after = max(0, 60 - (current_time - oldest_timestamp))
            return True, "User rate limit exceeded", retry_after
        
        # Check guild rate limit
        if guild_count >= self.guild_rate_limit:
            oldest_timestamp = min([req[0] for req in self.guild_requests[guild_id]]) if self.guild_requests[guild_id] else current_time
            retry_after = max(0, 60 - (current_time - oldest_timestamp))
            return True, "Guild rate limit exceeded", retry_after
        
        # Check global rate limit
        if global_count >= self.global_rate_limit:
            oldest_timestamp = min([req[0] for req in self.global_requests]) if self.global_requests else current_time
            retry_after = max(0, 60 - (current_time - oldest_timestamp))
            return True, "Global rate limit exceeded", retry_after
        
        # Not rate limited
        return False, None, 0
    
    def add_request(self, user_id, guild_id, command_name=None):
        """
        Record a request.
        
        Args:
            user_id: The user's ID
            guild_id: The guild's ID
            command_name: Optional command name for command-specific tracking
        """
        current_time = time.time()
        
        # Add to user requests
        self.user_requests[user_id].append((current_time, 1))
        
        # Add to guild requests
        self.guild_requests[guild_id].append((current_time, 1))
        
        # Add to global requests
        self.global_requests.append((current_time, 1))
        
        # Add to command-specific requests if applicable
        if command_name:
            self.command_requests[command_name].append((current_time, 1))
    
    def set_rate_limits(self, user_limit=None, guild_limit=None, global_limit=None, command_limits=None):
        """
        Update rate limits.
        
        Args:
            user_limit: Requests per user per minute
            guild_limit: Requests per guild per minute
            global_limit: Total requests per minute
            command_limits: Dict of {command_name: limit_per_minute}
        """
        if user_limit is not None:
            self.user_rate_limit = user_limit
        
        if guild_limit is not None:
            self.guild_rate_limit = guild_limit
        
        if global_limit is not None:
            self.global_rate_limit = global_limit
        
        if command_limits is not None:
            self.command_rate_limits.update(command_limits)
