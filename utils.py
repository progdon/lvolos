import logging
import discord
from datetime import datetime, timedelta
from models import get_guild_config, get_user_stats

logger = logging.getLogger(__name__)

def format_time(seconds):
    """Format seconds into a human-readable time format."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"
    elif minutes > 0:
        return f"{int(minutes)}м {int(seconds)}с"
    else:
        return f"{int(seconds)}с"

def format_contribution(contribution):
    """Format a contribution value with 2 decimal places."""
    return f"{contribution:.2f}"

async def send_level_up_message(bot, user_id, guild_id, new_level):
    """Send a level up message to the user or specified channel."""
    try:
        # Get guild and user objects
        guild = bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Could not find guild with ID {guild_id}")
            return
        
        member = guild.get_member(user_id)
        if not member:
            logger.error(f"Could not find member with ID {user_id} in guild {guild.name}")
            return
        
        # Get guild config
        config = get_guild_config(guild_id)
        
        # Check if level up messages are disabled
        if config['levelup_destination'] == 'disable':
            return
        
        # Get user stats
        stats = get_user_stats(user_id, guild_id)
        
        # Format the message
        message_template = config.get('levelup_message_template', 'Поздравляем {user}! Вы достигли уровня {level}!')
        message = message_template.replace('{user}', member.mention)
        message = message.replace('{level}', str(new_level))
        if stats and 'contribution' in stats:
            message = message.replace('{contribution}', format_contribution(stats['contribution']))
        else:
            message = message.replace('{contribution}', '0.00')
        
        # Send the message
        if config['levelup_destination'] == 'dm':
            # Send as DM
            try:
                await member.send(message)
            except discord.Forbidden:
                logger.error(f"Cannot send DM to {member.name}. They might have DMs disabled.")
            except Exception as e:
                logger.error(f"Error sending DM to {member.name}: {e}")
        else:
            # Send to channel
            channel_id = config['levelup_channel_id']
            if not channel_id:
                # If no channel specified, try to find a general or first text channel
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        channel_id = channel.id
                        break
            
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel and channel.permissions_for(guild.me).send_messages:
                    await channel.send(message)
                else:
                    logger.error(f"Cannot send message to channel ID {channel_id} in guild {guild.name}")
            else:
                logger.error(f"No suitable channel found to send level up message in guild {guild.name}")
    
    except Exception as e:
        logger.error(f"Error sending level up message: {e}")

# Функции для работы с ролями уровня были удалены по запросу

def has_admin_permission(ctx):
    """Check if the user has admin permissions or the configured admin role."""
    # Always allow server administrators
    if ctx.author.guild_permissions.administrator:
        return True
    
    # Also check for specific admin role in the config
    config = get_guild_config(ctx.guild.id)
    admin_role_id = config.get('admin_role_id')
    
    if admin_role_id:
        return any(role.id == admin_role_id for role in ctx.author.roles)
    
    return False

def get_next_level_info(user_stats, guild_id):
    """Get information about the next level for a user."""
    config = get_guild_config(guild_id)
    thresholds = config['level_thresholds']
    
    current_level = user_stats['current_level']
    contribution = user_stats['contribution']
    
    # Find the next level threshold
    next_level = None
    next_threshold = None
    
    # Sort thresholds by level number
    sorted_thresholds = sorted([(int(level), req) for level, req in thresholds.items()])
    
    for level, required in sorted_thresholds:
        if level > current_level and (next_level is None or level < next_level):
            next_level = level
            next_threshold = required
    
    if next_level is None:
        # User is at max level
        return {
            'next_level': None,
            'next_threshold': None,
            'contribution_needed': None,
            'progress_percentage': 100
        }
    
    # Calculate progress
    contribution_needed = next_threshold - contribution
    
    # Calculate percentage progress to next level
    if current_level == 0:
        # For level 0, calculate progress directly to level 1
        current_threshold = 0
    else:
        # Get the threshold for the current level
        current_threshold = next((req for lvl, req in sorted_thresholds if int(lvl) == current_level), 0)
    
    # Защита от None значений
    if next_threshold is None:
        next_threshold = current_threshold + 1  # Если нет следующего порога, добавляем 1
        
    if current_threshold is None:
        current_threshold = 0  # Если нет текущего порога, используем 0
    
    # Calculate progress percentage
    if next_threshold - current_threshold > 0:
        progress = contribution - current_threshold
        total_needed = next_threshold - current_threshold
        progress_percentage = min(100, max(0, (progress / total_needed) * 100))
    else:
        progress_percentage = 100
    
    return {
        'next_level': next_level,
        'next_threshold': next_threshold,
        'contribution_needed': contribution_needed,
        'progress_percentage': progress_percentage
    }

def get_progress_bar(percentage, length=10):
    """Create a text-based progress bar of the specified length."""
    filled = int(length * percentage / 100)
    empty = length - filled
    return '█' * filled + '░' * empty
