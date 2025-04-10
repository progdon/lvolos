"""
Скрипт для обновления пороговых уровней в базе данных.
"""

import logging
import json
from models import get_db_connection

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def update_all_level_thresholds():
    """Обновить пороги уровней для всех серверов до нового формата."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Новые пороги уровней из скриншота
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
    
    # Обновляем уровни пользователей на основе новых порогов
    cursor.execute(
        """
        SELECT guild_id, user_id, total_seconds 
        FROM UserStats
        """
    )
    
    user_records = cursor.fetchall()
    updated_count = 0
    
    for guild_id, user_id, total_seconds in user_records:
        contribution = total_seconds / 3600  # Перевод секунд в часы
        
        # Находим максимальный уровень, который должен быть у пользователя
        new_level = 0
        for level, required in new_thresholds.items():
            if contribution >= required and int(level) > new_level:
                new_level = int(level)
        
        # Обновляем уровень
        cursor.execute(
            """
            UPDATE UserStats
            SET current_level = %s
            WHERE guild_id = %s AND user_id = %s
            """,
            (new_level, guild_id, user_id)
        )
        updated_count += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"Обновлены пороги уровней для всех серверов")
    logger.info(f"Пересчитаны уровни для {updated_count} пользователей")
    
    return True

if __name__ == "__main__":
    update_all_level_thresholds()