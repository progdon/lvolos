import os
import sys
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify
import psycopg2
import psycopg2.extras
from werkzeug.middleware.proxy_fix import ProxyFix
from bot import bot
from models import get_db_connection, get_guild_config, get_leaderboard, get_user_stats
import utils

# Настройка уровня логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Create Flask app with static files directory
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Маршруты для веб-интерфейса
@app.route('/')
def index():
    """Домашняя страница со списком серверов"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Получаем список всех серверов с учетом структуры таблицы
            cursor.execute("""
                SELECT gs.guild_id, COUNT(DISTINCT us.user_id) AS user_count,
                       SUM(us.total_seconds)/3600.0 AS total_contribution
                FROM GuildSettings gs
                LEFT JOIN UserStats us ON gs.guild_id = us.guild_id
                GROUP BY gs.guild_id
                ORDER BY user_count DESC
            """)
            guilds = cursor.fetchall()
            
            # Получаем конфигурацию для каждого сервера
            guild_list = []
            for guild in guilds:
                config = get_guild_config(guild['guild_id'])
                guild_data = dict(guild)
                
                # Добавляем ключи 'id' и 'name' для совместимости с шаблоном
                guild_data['id'] = guild_data['guild_id']
                
                # Получаем имя сервера из бота если возможно
                server = bot.get_guild(guild['guild_id'])
                if server:
                    guild_data['guild_name'] = server.name
                    guild_data['name'] = server.name  # Для шаблона
                    guild_data['guild_icon'] = str(server.icon.url) if server.icon else None
                else:
                    guild_data['guild_name'] = f"Сервер {guild['guild_id']}"
                    guild_data['name'] = f"Сервер {guild['guild_id']}"  # Для шаблона
                    guild_data['guild_icon'] = None
                guild_data['unit_name'] = config.get('contribution_unit_name', 'часов')
                guild_list.append(guild_data)
            
        conn.close()
        return render_template('index.html', guilds=guild_list)
    except Exception as e:
        logger.error(f"Ошибка на главной странице: {e}")
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1 {{ color: #e74c3c; }}
                .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Произошла ошибка</h1>
            <div class="error">{str(e)}</div>
            <p><a href="/">Вернуться на главную</a></p>
        </body>
        </html>
        """
        return html_error

@app.route('/guild/<int:guild_id>')
def guild_stats(guild_id):
    """Страница статистики сервера"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Получаем информацию о сервере из GuildSettings
            cursor.execute("""
                SELECT guild_id FROM GuildSettings WHERE guild_id = %s
            """, (guild_id,))
            guild_record = cursor.fetchone()
            
            if not guild_record:
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                        h1 {{ color: #e74c3c; }}
                        .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
                    </style>
                </head>
                <body>
                    <h1>Произошла ошибка</h1>
                    <div class="error">Сервер не найден</div>
                    <p><a href="/">Вернуться на главную</a></p>
                </body>
                </html>
                """
                return html_error
            
            # Получаем данные о сервере из бота если возможно
            server = bot.get_guild(guild_id)
            
            # Создаем объект с данными сервера
            guild = {
                'guild_id': guild_id,
                'guild_name': server.name if server else f"Сервер {guild_id}",
                'guild_icon': str(server.icon.url) if server and server.icon else None,
            }
            
            # Получаем конфигурацию сервера
            config = get_guild_config(guild_id)
            
            # Получаем лидеров сервера
            leaderboard = get_leaderboard(guild_id, limit=100)
            
            # Получаем общую статистику
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as user_count,
                       SUM(total_seconds)/3600.0 as total_contribution,
                       SUM(total_seconds) as total_time,
                       MAX(current_level) as max_level
                FROM UserStats
                WHERE guild_id = %s
            """, (guild_id,))
            stats = cursor.fetchone()
        
        conn.close()
        return render_template('guild.html', 
                              guild=guild, 
                              guild_id=guild_id,  # Добавляем guild_id отдельно
                              guild_name=guild['guild_name'],  # Добавляем guild_name отдельно
                              config=config, 
                              leaderboard=leaderboard,
                              stats=stats)
    except Exception as e:
        logger.error(f"Ошибка на странице сервера: {e}")
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1 {{ color: #e74c3c; }}
                .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Произошла ошибка</h1>
            <div class="error">{str(e)}</div>
            <p><a href="/">Вернуться на главную</a></p>
        </body>
        </html>
        """
        return html_error

@app.route('/guild/<int:guild_id>/user/<int:user_id>')
def user_stats(guild_id, user_id):
    """Страница статистики пользователя на сервере"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Проверяем существование сервера
            cursor.execute("""
                SELECT guild_id FROM GuildSettings WHERE guild_id = %s
            """, (guild_id,))
            guild_record = cursor.fetchone()
            
            if not guild_record:
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                        h1 {{ color: #e74c3c; }}
                        .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
                    </style>
                </head>
                <body>
                    <h1>Произошла ошибка</h1>
                    <div class="error">Сервер не найден</div>
                    <p><a href="/">Вернуться на главную</a></p>
                </body>
                </html>
                """
                return html_error
            
            # Получаем данные о сервере из бота если возможно
            server = bot.get_guild(guild_id)
            
            # Создаем объект с данными сервера
            guild = {
                'guild_id': guild_id,
                'guild_name': server.name if server else f"Сервер {guild_id}",
                'guild_icon': str(server.icon.url) if server and server.icon else None,
            }
            
            # Получаем статистику пользователя
            stats = get_user_stats(user_id, guild_id)
            
            if not stats:
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                        h1 {{ color: #e74c3c; }}
                        .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
                    </style>
                </head>
                <body>
                    <h1>Произошла ошибка</h1>
                    <div class="error">Пользователь не найден</div>
                    <p><a href="/guild/{guild_id}">Вернуться к статистике сервера</a></p>
                </body>
                </html>
                """
                return html_error
            
            # Получаем конфигурацию сервера
            config = get_guild_config(guild_id)
            
            # Получаем ранг пользователя
            cursor.execute("""
                SELECT COUNT(*) + 1 as rank
                FROM UserStats
                WHERE guild_id = %s AND total_seconds > 
                    (SELECT total_seconds FROM UserStats WHERE guild_id = %s AND user_id = %s)
            """, (guild_id, guild_id, user_id))
            rank_result = cursor.fetchone()
            rank = rank_result['rank'] if rank_result else 1
            
        conn.close()
        return render_template('user.html', 
                              guild=guild, 
                              user=stats,
                              config=config,
                              rank=rank)
    except Exception as e:
        logger.error(f"Ошибка на странице пользователя: {e}")
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1 {{ color: #e74c3c; }}
                .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Произошла ошибка</h1>
            <div class="error">{str(e)}</div>
            <p><a href="/">Вернуться на главную</a></p>
        </body>
        </html>
        """
        return html_error

@app.route('/card_images')
def list_card_images():
    """Страница с примерами карточек (устаревшая, перенаправляет на главную)"""
    return redirect(url_for('index'))

@app.route('/levels')
def levels():
    """Страница с информацией о порогах уровней"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Получаем информацию о всех серверах с учетом изменений в схеме
            cursor.execute("""
                SELECT guild_id FROM GuildSettings
            """)
            guilds_records = cursor.fetchall()
            
            guild_list = []
            for guild_record in guilds_records:
                guild_id = guild_record['guild_id']
                
                # Получаем данные о сервере из бота если возможно
                server = bot.get_guild(guild_id)
                guild_name = server.name if server else f"Сервер {guild_id}"
                
                # Получаем конфигурацию для сервера
                config = get_guild_config(guild_id)
                
                # Преобразуем JSON-строку в словарь
                level_thresholds = config.get('level_thresholds', {})
                
                guild_data = {
                    'id': guild_id,
                    'name': guild_name,
                    'unit_name': config.get('contribution_unit_name', 'часов'),
                    'thresholds': level_thresholds
                }
                guild_list.append(guild_data)
                
        conn.close()
        return render_template('levels.html', guilds=guild_list)
    except Exception as e:
        logger.error(f"Ошибка на странице уровней: {e}")
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ошибка</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                h1 {{ color: #e74c3c; }}
                .error {{ background: #f8d7da; border-left: 5px solid #e74c3c; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Произошла ошибка</h1>
            <div class="error">{str(e)}</div>
            <p><a href="/">Вернуться на главную</a></p>
        </body>
        </html>
        """
        return html_error

def run_flask():
    """Запуск веб-сервера Flask"""
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask: {e}")

def run_bot():
    """Запуск Discord бота"""
    print("Запуск Discord бота...")
    # Добавляем явный print для отладки запуска бота
    try:
        bot.run(os.environ.get('DISCORD_TOKEN'))
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    # Запуск Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запуск бота в основном потоке
    run_bot()
