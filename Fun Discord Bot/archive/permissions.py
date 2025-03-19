"""
Permissions module for handling user permissions in Discord.
"""
import discord
from enum import Enum, auto

class PermissionLevel(Enum):
    """Enum for permission levels."""
    EVERYONE = auto()
    MODERATOR = auto()
    ADMIN = auto()
    SERVER_OWNER = auto()

def get_user_permission_level(member: discord.Member) -> PermissionLevel:
    """
    Determine the permission level of a Discord member.
    
    Args:
        member: The Discord member to check
        
    Returns:
        PermissionLevel: The member's permission level
    """
    # Check if user is the server owner
    if member.guild.owner_id == member.id:
        return PermissionLevel.SERVER_OWNER
    
    # Check if user has administrator permission
    if member.guild_permissions.administrator:
        return PermissionLevel.ADMIN
    
    # Check if user has moderator permissions
    if (member.guild_permissions.manage_messages or 
        member.guild_permissions.ban_members or 
        member.guild_permissions.kick_members or 
        member.guild_permissions.manage_channels):
        return PermissionLevel.MODERATOR
    
    # Default permission level
    return PermissionLevel.EVERYONE

def has_permission(member: discord.Member, required_level: PermissionLevel) -> bool:
    """
    Check if a member has the required permission level.
    
    Args:
        member: The Discord member to check
        required_level: The required permission level
        
    Returns:
        bool: True if the member has the required permission level, False otherwise
    """
    user_level = get_user_permission_level(member)
    
    # Compare enum values (higher values = higher permissions)
    return user_level.value >= required_level.value

def check_permission(interaction: discord.Interaction, required_level: PermissionLevel) -> bool:
    """
    Check if the user who triggered an interaction has the required permission level.
    
    Args:
        interaction: The Discord interaction
        required_level: The required permission level
        
    Returns:
        bool: True if the user has the required permission level, False otherwise
    """
    if interaction.guild is None:
        # No permissions in DMs
        return False
    
    return has_permission(interaction.user, required_level)
