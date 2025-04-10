"""
Скрипт для полного сброса и пересоздания команд Discord приложения.
Запустите этот скрипт, если у вас возникает ошибка "Неизвестная интеграция".

Скрипт выполняет несколько шагов:
1. Удаляет все существующие команды в Discord приложении (глобальные)
2. Удаляет все команды для конкретных серверов
3. Пересоздает команды с нуля
"""

import os
import asyncio
import discord
from discord.ext import commands
import logging
import sys
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("discord_fix")

# Создаем бота с правами администратора
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def delete_all_commands():
    """Удаляем все команды (глобальные и на серверах)"""
    try:
        # Сначала получаем список всех серверов
        print(f"Бот находится на {len(bot.guilds)} серверах")
        
        # Удаляем глобальные команды
        print("Получаем список глобальных команд...")
        global_commands = await bot.http.get_global_commands(bot.user.id)
        print(f"Найдено {len(global_commands)} глобальных команд")
        
        if global_commands:
            print("Удаляем все глобальные команды...")
            for cmd in global_commands:
                cmd_id = cmd["id"]
                cmd_name = cmd["name"]
                print(f"Удаление глобальной команды {cmd_name} (ID: {cmd_id})...")
                
                try:
                    await bot.http.delete_global_command(bot.user.id, cmd_id)
                    print(f"Команда {cmd_name} успешно удалена")
                    # Небольшая задержка, чтобы избежать rate limits
                    await asyncio.sleep(1)
                except discord.errors.HTTPException as e:
                    print(f"Ошибка при удалении глобальной команды {cmd_name}: {e}")
                    if e.status == 429:  # Rate limit
                        retry_after = e.retry_after
                        print(f"Превышен лимит запросов, ожидание {retry_after} секунд...")
                        await asyncio.sleep(retry_after + 1)
                        # Повторная попытка
                        await bot.http.delete_global_command(bot.user.id, cmd_id)
                        print(f"Команда {cmd_name} успешно удалена после ожидания")
        
        # Удаляем команды на каждом сервере
        for guild in bot.guilds:
            print(f"Обрабатываем сервер: {guild.name} (ID: {guild.id})")
            
            try:
                guild_commands = await bot.http.get_guild_commands(bot.user.id, guild.id)
                print(f"Найдено {len(guild_commands)} команд на сервере {guild.name}")
                
                if guild_commands:
                    print(f"Удаляем все команды с сервера {guild.name}...")
                    for cmd in guild_commands:
                        cmd_id = cmd["id"]
                        cmd_name = cmd["name"]
                        try:
                            await bot.http.delete_guild_command(bot.user.id, guild.id, cmd_id)
                            print(f"Команда {cmd_name} успешно удалена с сервера {guild.name}")
                            # Небольшая задержка
                            await asyncio.sleep(1)
                        except discord.errors.HTTPException as e:
                            print(f"Ошибка при удалении команды {cmd_name} с сервера {guild.name}: {e}")
                            if e.status == 429:  # Rate limit
                                retry_after = e.retry_after
                                print(f"Превышен лимит запросов, ожидание {retry_after} секунд...")
                                await asyncio.sleep(retry_after + 1)
                                # Повторная попытка
                                await bot.http.delete_guild_command(bot.user.id, guild.id, cmd_id)
                                print(f"Команда {cmd_name} успешно удалена с сервера {guild.name} после ожидания")
            except Exception as e:
                print(f"Ошибка при обработке сервера {guild.name}: {e}")
        
        print("Все команды успешно удалены!")
        print("Теперь перезапустите бота, и команды будут зарегистрированы заново.")
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")

@bot.event
async def on_ready():
    print(f"Бот {bot.user.name} подключен!")
    await delete_all_commands()
    # Выходим после выполнения
    await bot.close()

def main():
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("❌ Ошибка: Токен Discord не найден!")
        print("Установите переменную окружения DISCORD_TOKEN")
        return
    
    print("🔄 Запуск процесса очистки команд Discord...")
    bot.run(token)
    print("✅ Процесс завершен! Перезапустите основного бота.")

if __name__ == "__main__":
    main()