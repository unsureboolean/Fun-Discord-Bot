from enum import Enum, auto

class PermissionLevel(Enum):
    """Enum for permission levels."""
    EVERYONE = 0
    MODERATOR = 1
    ADMIN = 2
    SERVER_OWNER = 3

def check_permission(interaction, required_level):
    """
    Check if a user has the required permission level.
    
    This is a mock version for testing that doesn't require the discord module.
    In the actual implementation, this function checks the user's permissions
    in the Discord server.
    
    Args:
        interaction: Discord interaction object
        required_level: Required permission level
        
    Returns:
        bool: Whether the user has the required permission
    """
    # This is just a placeholder for testing
    return True
