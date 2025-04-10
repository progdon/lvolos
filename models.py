import os
import psycopg2
import psycopg2.extras
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Получаем данные подключения к PostgreSQL из переменных окружения
DATABASE_URL = os.environ.get('DATABASE_URL')

# Функция для получения соединения с базой данных
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise

def update_all_level_thresholds(cursor=None):
    """Обновить пороги уровней для всех серверов до нового формата."""
    close_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        close_conn = True
    
    # Новые пороги уровней
    new_thresholds = {
        "1": 0, "2": 1, "3": 4, "4": 13, "5": 30, 
        "6": 57, "7": 97, "8": 152, "9": 224, "10": 317, 
        "11": 431, "12": 571, "13": 737, "14": 933, "15": 1161, 
        "16": 1424, "17": 1723, "18": 2061, "19": 2441, "20": 2864, 
        "21": 3334, "22": 3853, "23": 4422, "24": 5046, "25": 5725, 
        "26": 6463, "27": 7261, "28": 8122, "29": 9049, "30": 10044, 
        "31": 11109, "32": 12247, "33": 13460, "34": 14750, "35": 16121, 
        "36": 17573, "37": 19111, "38": 20735, "39": 22449, "40": 24255, 
        "41": 26156, "42": 28153, "43": 30249, "44": 32447, "45": 34748
    }
    
    # Сериализуем в JSON
    thresholds_json = json.dumps(new_thresholds)
    
    # Обновляем для всех серверов
    cursor.execute(
        """
        UPDATE GuildSettings 
        SET level_thresholds = %s
        """,
        (thresholds_json,)
    )
    
    logger.info(f"Обновлены пороги уровней для всех серверов")
    
    if close_conn:
        conn.close()
        
    return True

def init_db():
    """Initialize the database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create GuildSettings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS GuildSettings (
        guild_id BIGINT PRIMARY KEY,
        track_channels TEXT DEFAULT 'all',
        ignore_channels TEXT DEFAULT '[]',
        count_muted INTEGER DEFAULT 1,
        count_deafened INTEGER DEFAULT 1,
        count_server_muted INTEGER DEFAULT 1,
        count_server_deafened INTEGER DEFAULT 1,
        contribution_unit_name TEXT DEFAULT 'часов',
        level_thresholds TEXT DEFAULT '{"1": 0, "2": 1, "3": 4, "4": 13, "5": 30, "6": 57, "7": 97, "8": 152, "9": 224, "10": 317, "11": 431, "12": 571, "13": 737, "14": 933, "15": 1161, "16": 1424, "17": 1723, "18": 2061, "19": 2441, "20": 2864, "21": 3334, "22": 3853, "23": 4422, "24": 5046, "25": 5725, "26": 6463, "27": 7261, "28": 8122, "29": 9049, "30": 10044, "31": 11109, "32": 12247, "33": 13460, "34": 14750, "35": 16121, "36": 17573, "37": 19111, "38": 20735, "39": 22449, "40": 24255, "41": 26156, "42": 28153, "43": 30249, "44": 32447, "45": 34748}',
        levelup_message TEXT DEFAULT 'Поздравляем, {user}! Вы достигли {level} уровня с вкладом {contribution}.',
        levelup_destination TEXT DEFAULT 'channel',
        levelup_channel_id BIGINT DEFAULT NULL
    )
    ''')
    
    # Обновить пороги уровней для существующих серверов
    update_all_level_thresholds(cursor)
    
    # Create UserStats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS UserStats (
        user_id BIGINT,
        guild_id BIGINT,
        total_seconds BIGINT DEFAULT 0,
        current_level INTEGER DEFAULT 0,
        last_voice_join TEXT DEFAULT NULL,
        last_channel_id BIGINT DEFAULT NULL,
        PRIMARY KEY (user_id, guild_id)
    )
    ''')
    
    # Create ActiveUsers table to track currently active users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ActiveUsers (
        user_id BIGINT,
        guild_id BIGINT,
        channel_id BIGINT,
        join_time TEXT,
        is_muted INTEGER DEFAULT 0,
        is_deafened INTEGER DEFAULT 0,
        is_server_muted INTEGER DEFAULT 0,
        is_server_deafened INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )
    ''')
    
    conn.close()
    logger.info("Database initialized successfully.")

def create_default_guild_config(guild_id):
    """Create default configuration for a new guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if guild config already exists
    cursor.execute("SELECT guild_id FROM GuildSettings WHERE guild_id = %s", (guild_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO GuildSettings (guild_id) VALUES (%s)",
            (guild_id,)
        )
        logger.info(f"Created default configuration for guild {guild_id}")
    
    conn.close()

def get_guild_config(guild_id):
    """Get configuration for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM GuildSettings WHERE guild_id = %s", (guild_id,))
    row = cursor.fetchone()
    
    if row is None:
        # Create default config if it doesn't exist
        create_default_guild_config(guild_id)
        cursor.execute("SELECT * FROM GuildSettings WHERE guild_id = %s", (guild_id,))
        row = cursor.fetchone()
    
    # Get column names
    column_names = [desc[0] for desc in cursor.description]
    
    # Convert row to dictionary
    config = {}
    for i, column in enumerate(column_names):
        if column in ('track_channels', 'ignore_channels', 'level_thresholds'):
            # Parse JSON strings to Python objects
            try:
                config[column] = json.loads(row[i]) if row[i] else {}
            except json.JSONDecodeError:
                if column == 'track_channels' and row[i] == 'all':
                    config[column] = 'all'
                else:
                    config[column] = [] if column == 'ignore_channels' else {}
        else:
            config[column] = row[i]
    
    conn.close()
    return config

def update_guild_config(guild_id, setting, value):
    """Update a specific setting for a guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if the setting is one that needs to be JSON serialized
    if setting in ('track_channels', 'ignore_channels', 'level_thresholds'):
        if setting == 'track_channels' and value == 'all':
            # Special case for 'all' value
            serialized_value = 'all'
        else:
            # Convert to JSON string
            serialized_value = json.dumps(value)
        
        cursor.execute(
            f"UPDATE GuildSettings SET {setting} = %s WHERE guild_id = %s",
            (serialized_value, guild_id)
        )
    else:
        # Normal value, no need to serialize
        cursor.execute(
            f"UPDATE GuildSettings SET {setting} = %s WHERE guild_id = %s",
            (value, guild_id)
        )
    
    conn.close()
    return True

def record_user_join_voice(user_id, guild_id, channel_id, is_muted, is_deafened, is_server_muted, is_server_deafened):
    """Record when a user joins a voice channel."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    
    # Convert boolean values to integers (0/1) for PostgreSQL
    is_muted_int = 1 if is_muted else 0
    is_deafened_int = 1 if is_deafened else 0
    is_server_muted_int = 1 if is_server_muted else 0
    is_server_deafened_int = 1 if is_server_deafened else 0
    
    # Check if user is already in ActiveUsers
    cursor.execute(
        "SELECT user_id FROM ActiveUsers WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    if cursor.fetchone() is None:
        # Insert new record
        cursor.execute(
            """
            INSERT INTO ActiveUsers 
            (user_id, guild_id, channel_id, join_time, is_muted, is_deafened, is_server_muted, is_server_deafened)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, guild_id, channel_id, current_time, is_muted_int, is_deafened_int, is_server_muted_int, is_server_deafened_int)
        )
    else:
        # Update existing record
        cursor.execute(
            """
            UPDATE ActiveUsers 
            SET channel_id = %s, join_time = %s, is_muted = %s, is_deafened = %s, is_server_muted = %s, is_server_deafened = %s
            WHERE user_id = %s AND guild_id = %s
            """,
            (channel_id, current_time, is_muted_int, is_deafened_int, is_server_muted_int, is_server_deafened_int, user_id, guild_id)
        )
    
    # Also update the UserStats table
    cursor.execute(
        "SELECT user_id FROM UserStats WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    if cursor.fetchone() is None:
        # User doesn't have stats yet, create them
        cursor.execute(
            """
            INSERT INTO UserStats 
            (user_id, guild_id, total_seconds, current_level, last_voice_join, last_channel_id)
            VALUES (%s, %s, 0, 0, %s, %s)
            """,
            (user_id, guild_id, current_time, channel_id)
        )
    else:
        # Update last join time
        cursor.execute(
            """
            UPDATE UserStats 
            SET last_voice_join = %s, last_channel_id = %s
            WHERE user_id = %s AND guild_id = %s
            """,
            (current_time, channel_id, user_id, guild_id)
        )
    
    conn.close()

def record_user_leave_voice(user_id, guild_id):
    """Record when a user leaves a voice channel and calculate time spent."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the guild config to check settings
    config = get_guild_config(guild_id)
    
    # Get active user record
    cursor.execute(
        """
        SELECT channel_id, join_time, is_muted, is_deafened, is_server_muted, is_server_deafened 
        FROM ActiveUsers 
        WHERE user_id = %s AND guild_id = %s
        """,
        (user_id, guild_id)
    )
    
    active_record = cursor.fetchone()
    if not active_record:
        # User wasn't in active records
        conn.close()
        return
    
    channel_id, join_time, is_muted, is_deafened, is_server_muted, is_server_deafened = active_record
    
    # Check if we should count time based on user's state and config
    should_count = True
    
    # Check if user was in an ignored channel
    ignore_channels = config['ignore_channels']
    if channel_id in ignore_channels:
        should_count = False
    
    # Check track channels if not set to 'all'
    if config['track_channels'] != 'all' and channel_id not in config['track_channels']:
        should_count = False
    
    # Check mute/deafen settings
    if is_muted and not config['count_muted']:
        should_count = False
    if is_deafened and not config['count_deafened']:
        should_count = False
    if is_server_muted and not config['count_server_muted']:
        should_count = False
    if is_server_deafened and not config['count_server_deafened']:
        should_count = False
    
    if should_count:
        # Calculate time spent in voice
        join_dt = datetime.fromisoformat(join_time)
        leave_dt = datetime.now()
        time_spent = (leave_dt - join_dt).total_seconds()
        
        if time_spent > 0:
            # Add time to user's total
            cursor.execute(
                """
                UPDATE UserStats 
                SET total_seconds = total_seconds + %s, last_voice_join = NULL, last_channel_id = NULL
                WHERE user_id = %s AND guild_id = %s
                """,
                (time_spent, user_id, guild_id)
            )
    else:
        # Just clear the last_voice_join without adding time
        cursor.execute(
            """
            UPDATE UserStats 
            SET last_voice_join = NULL, last_channel_id = NULL
            WHERE user_id = %s AND guild_id = %s
            """,
            (user_id, guild_id)
        )
    
    # Remove user from active users
    cursor.execute(
        "DELETE FROM ActiveUsers WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    # Update user's level
    update_user_level(cursor, user_id, guild_id, config)
    
    conn.close()

def update_user_voice_state(user_id, guild_id, is_muted, is_deafened, is_server_muted, is_server_deafened):
    """Update a user's voice state in the ActiveUsers table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert boolean values to integers (0/1) for PostgreSQL
    is_muted_int = 1 if is_muted else 0
    is_deafened_int = 1 if is_deafened else 0
    is_server_muted_int = 1 if is_server_muted else 0
    is_server_deafened_int = 1 if is_server_deafened else 0
    
    cursor.execute(
        """
        UPDATE ActiveUsers 
        SET is_muted = %s, is_deafened = %s, is_server_muted = %s, is_server_deafened = %s
        WHERE user_id = %s AND guild_id = %s
        """,
        (is_muted_int, is_deafened_int, is_server_muted_int, is_server_deafened_int, user_id, guild_id)
    )
    
    conn.close()

def get_user_stats(user_id, guild_id):
    """Get stats for a specific user on a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT total_seconds, current_level FROM UserStats WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    result = cursor.fetchone()
    
    if result is None:
        # User doesn't have stats yet
        stats = {
            'user_id': user_id,
            'guild_id': guild_id,
            'total_seconds': 0,
            'current_level': 0,
            'contribution': 0
        }
    else:
        total_seconds, current_level = result
        # Convert seconds to contribution (1 hour = 1 contribution)
        contribution = total_seconds / 3600
        
        stats = {
            'user_id': user_id,
            'guild_id': guild_id,
            'total_seconds': total_seconds,
            'current_level': current_level,
            'contribution': contribution
        }
    
    conn.close()
    return stats

def get_leaderboard(guild_id, limit=10, offset=0):
    """Get the top users by contribution."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT user_id, total_seconds, current_level 
        FROM UserStats 
        WHERE guild_id = %s 
        ORDER BY total_seconds DESC
        LIMIT %s OFFSET %s
        """,
        (guild_id, limit, offset)
    )
    
    results = cursor.fetchall()
    
    leaderboard = []
    for user_id, total_seconds, current_level in results:
        contribution = total_seconds / 3600
        leaderboard.append({
            'user_id': user_id,
            'contribution': contribution,
            'level': current_level
        })
    
    conn.close()
    return leaderboard

def update_user_level(cursor, user_id, guild_id, config=None):
    """Update a user's level based on their contribution."""
    if config is None:
        # Get guild config if not provided
        config = get_guild_config(guild_id)
    
    # Get user's current stats
    cursor.execute(
        "SELECT total_seconds, current_level FROM UserStats WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    result = cursor.fetchone()
    if result is None:
        return None
    
    total_seconds, current_level = result
    contribution = total_seconds / 3600  # Convert seconds to hours/contribution
    
    # Get level thresholds
    thresholds = config['level_thresholds']
    
    # Find the highest level the user should have
    new_level = 0
    for level, required_contribution in thresholds.items():
        level_num = int(level)
        if contribution >= required_contribution and level_num > new_level:
            new_level = level_num
    
    # Check if level increased
    level_increased = new_level > current_level
    
    if level_increased:
        # Update user's level
        cursor.execute(
            "UPDATE UserStats SET current_level = %s WHERE user_id = %s AND guild_id = %s",
            (new_level, user_id, guild_id)
        )
        
        return new_level
    
    return None

def set_user_contribution(user_id, guild_id, contribution):
    """Manually set a user's contribution amount."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert contribution to seconds
    total_seconds = contribution * 3600
    
    # Get guild config
    config = get_guild_config(guild_id)
    
    # Update user's total seconds
    cursor.execute(
        """
        UPDATE UserStats 
        SET total_seconds = %s
        WHERE user_id = %s AND guild_id = %s
        """,
        (total_seconds, user_id, guild_id)
    )
    
    affected = cursor.rowcount
    
    if affected == 0:
        # User doesn't have stats yet, create them
        cursor.execute(
            """
            INSERT INTO UserStats 
            (user_id, guild_id, total_seconds, current_level)
            VALUES (%s, %s, %s, 0)
            """,
            (user_id, guild_id, total_seconds)
        )
    
    # Update user's level
    new_level = update_user_level(cursor, user_id, guild_id, config)
    
    conn.close()
    
    return new_level

def adjust_user_contribution(user_id, guild_id, adjustment):
    """Adjust a user's contribution by the given amount."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert adjustment to seconds
    seconds_adjustment = adjustment * 3600
    
    # Get current stats
    cursor.execute(
        "SELECT total_seconds FROM UserStats WHERE user_id = %s AND guild_id = %s",
        (user_id, guild_id)
    )
    
    result = cursor.fetchone()
    
    if result is None:
        # User doesn't have stats yet, create them
        total_seconds = max(0, seconds_adjustment)  # Don't allow negative
        cursor.execute(
            """
            INSERT INTO UserStats 
            (user_id, guild_id, total_seconds, current_level)
            VALUES (%s, %s, %s, 0)
            """,
            (user_id, guild_id, total_seconds)
        )
    else:
        total_seconds = result[0]
        new_total = max(0, total_seconds + seconds_adjustment)  # Don't allow negative
        
        cursor.execute(
            """
            UPDATE UserStats 
            SET total_seconds = %s
            WHERE user_id = %s AND guild_id = %s
            """,
            (new_total, user_id, guild_id)
        )
    
    # Get guild config
    config = get_guild_config(guild_id)
    
    # Update user's level
    new_level = update_user_level(cursor, user_id, guild_id, config)
    
    conn.close()
    
    return new_level

def set_user_level(user_id, guild_id, level):
    """Manually set a user's level."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update user's level
    cursor.execute(
        """
        UPDATE UserStats 
        SET current_level = %s
        WHERE user_id = %s AND guild_id = %s
        """,
        (level, user_id, guild_id)
    )
    
    if cursor.rowcount == 0:
        # User doesn't have stats yet, create them
        cursor.execute(
            """
            INSERT INTO UserStats 
            (user_id, guild_id, total_seconds, current_level)
            VALUES (%s, %s, 0, %s)
            """,
            (user_id, guild_id, level)
        )
    
    conn.close()
    
    return level

def reset_user_stats(user_id, guild_id):
    """Reset a user's stats to zero."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE UserStats 
        SET total_seconds = 0, current_level = 0
        WHERE user_id = %s AND guild_id = %s
        """,
        (user_id, guild_id)
    )
    
    conn.close()

def reset_guild_stats(guild_id):
    """Reset all users' stats in a guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE UserStats 
        SET total_seconds = 0, current_level = 0
        WHERE guild_id = %s
        """,
        (guild_id,)
    )
    
    cursor.execute(
        """
        DELETE FROM ActiveUsers 
        WHERE guild_id = %s
        """,
        (guild_id,)
    )
    
    conn.close()
