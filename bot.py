import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
from models import init_db

logger = logging.getLogger(__name__)

# Настройка необходимых разрешений для бота
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True  # Это необходимо для отслеживания голосовых каналов
intents.message_content = True  # Это необходимо для команд

# Опциональные разрешения - будут использоваться только если включены в Developer Portal
try:
    intents.members = True  # Привилегированное разрешение - может потребовать включения в Developer Portal
except:
    pass  # Если не удалось включить, продолжаем без него

# Создание экземпляра бота с поддержкой слеш-команд
# Используем только префикс '!' для обычных команд, чтобы избежать конфликта со слеш-командами
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Инициализация базы данных
init_db()

@bot.event
async def on_ready():
    """Событие, срабатывающее когда бот готов и подключен к Discord."""
    if hasattr(bot, 'user') and bot.user:
        logger.info(f'Бот {bot.user.name} подключен к Discord!')
    else:
        logger.info('Бот запущен в режиме "только веб-интерфейс"')

    try:
        # Проверяем зарегистрированные команды и всегда синхронизируем для обновления
        commands = bot.tree.get_commands()
        if not commands:
            logger.warning("Команды не зарегистрированы, выполняем полную переинициализацию...")
            
            # Сначала выгружаем все модули если они были загружены
            for extension in list(bot.extensions.keys()):
                try:
                    await bot.unload_extension(extension)
                    logger.info(f"Выгружен модуль {extension}")
                except Exception as e:
                    logger.error(f"Ошибка при выгрузке {extension}: {e}")
            
            # Загружаем все модули заново
            await load_cogs()
        
        # Принудительная синхронизация команд при каждом запуске
        logger.info("Выполняем принудительную глобальную синхронизацию команд...")
        await asyncio.sleep(1)  # Даем время на инициализацию
        
        try:
            # Сначала удаляем все глобальные команды для обеспечения чистой синхронизации
            try:
                existing_commands = await bot.http.get_global_commands(bot.user.id)
                if existing_commands:
                    logger.info(f"Найдено {len(existing_commands)} существующих команд, выполняем полную пересинхронизацию")
            except Exception as e:
                logger.warning(f"Ошибка при получении списка команд: {e}")
                
            # Синхронизируем глобальные команды
            synced = await bot.tree.sync()
            logger.info(f"Синхронизировано глобальных команд: {len(synced)}")
            
            # Выводим список синхронизированных команд
            if synced:
                logger.info("Список синхронизированных команд:")
                for cmd in synced:
                    logger.info(f"- /{cmd.name}")
            else:
                logger.warning("После синхронизации список команд пуст! Выполняем экстренную переинициализацию...")
                # Повторная загрузка модулей и синхронизация
                await load_cogs()
                await asyncio.sleep(2)
                synced = await bot.tree.sync()
                logger.info(f"Экстренная синхронизация команд: {len(synced)}")
        except Exception as sync_error:
            logger.error(f"Критическая ошибка при синхронизации команд: {sync_error}")
            # В случае ошибки полностью перезапускаем процесс
            await load_cogs()
            await asyncio.sleep(3)
            synced = await bot.tree.sync()
            logger.info(f"Синхронизация после критической ошибки: {len(synced)}")
    except Exception as e:
        logger.error(f"Ошибка при проверке команд: {e}")

    try:
        # Подождем дополнительное время перед любыми операциями с API Discord
        # Это поможет избежать rate limiting при запуске
        await asyncio.sleep(5)

        logger.info("Загружаем cogs...")
        await load_cogs()

        await asyncio.sleep(2)

        logger.info("Проверяем существующие команды...")

        try:
            existing_commands = await bot.http.get_global_commands(bot.user.id)
            logger.info(f"Найдено {len(existing_commands)} существующих глобальных команд")

            # Даже если команды существуют, принудительно пересинхронизируем
            if existing_commands:
                logger.info("Существующие глобальные команды:")
                for cmd in existing_commands:
                    logger.info(f"- /{cmd['name']}")
                logger.info("Выполняем принудительную пересинхронизацию команд...")
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit error
                logger.warning(f"Rate limit при получении команд, ожидание: {e.retry_after} секунд")
                await asyncio.sleep(e.retry_after + 2)  # Добавляем 2 секунды запаса
            else:
                logger.warning(f"Ошибка при получении команд: {e}")

        logger.info("Синхронизируем команды с Discord...")
        await asyncio.sleep(5)

        logger.info("Загружаем модули перед синхронизацией...")
        await load_cogs()
        await asyncio.sleep(1)  # Небольшая пауза для стабильности

        logger.info("Синхронизируем команды...")
        try:
            synced = await bot.tree.sync()
            logger.info(f"Команды успешно синхронизированы: {len(synced)}")
            commands = bot.tree.get_commands()
            if commands:
                logger.info("Зарегистрированные команды:")
                for cmd in commands:
                    logger.info(f"- /{cmd.name}")
            else:
                logger.warning("Не обнаружено зарегистрированных команд!")
                await asyncio.sleep(2)
                synced = await bot.tree.sync()
                logger.info(f"Повторная синхронизация: {len(synced)} команд")
        except discord.errors.HTTPException as e:
            if e.status == 429:
                logger.warning(f"Rate limit при синхронизации, ожидание: {e.retry_after} секунд")
                await asyncio.sleep(e.retry_after + 2)
                synced = await bot.tree.sync()
                logger.info(f"Синхронизация после ожидания: {len(synced)} команд")
            else:
                raise

        await asyncio.sleep(5)
        
        commands = bot.tree.get_commands()
        if commands:
            logger.info("Зарегистрированы глобальные команды:")
            for cmd in commands:
                logger.info(f"- /{cmd.name}")
                if hasattr(cmd, 'commands') and cmd.commands:
                    for subcmd in cmd.commands:
                        logger.info(f"  - /{cmd.name} {subcmd.name}")
        else:
            logger.warning("Не зарегистрировано ни одной глобальной команды!")

    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="голосовые каналы"
        )
    )

async def load_cogs():
    """Загрузка всех модулей из директории cogs."""
    cog_modules = ["cogs.voice_tracking", "cogs.user_commands", "cogs.menu_commands", "cogs.admin_commands"]
    try:
        for module in cog_modules:
            # Проверяем, загружен ли уже модуль
            if module in bot.extensions:
                logger.info(f"Модуль {module} уже загружен, пропускаем...")
                continue
                
            try:
                logger.info(f"Загрузка модуля {module}...")
                await bot.load_extension(module)
                logger.info(f"Модуль {module} успешно загружен")
            except Exception as module_error:
                logger.error(f"Ошибка при загрузке модуля {module}: {module_error}")
                
        logger.info("Загрузка модулей завершена.")
        
        # Проверяем все загруженные модули
        logger.info(f"Загруженные модули: {', '.join(bot.extensions.keys())}")
        logger.info(f"Загруженные cogs: {', '.join(bot.cogs.keys())}")
        
    except Exception as e:
        logger.error(f"Глобальная ошибка при загрузке модулей: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Отсутствует обязательный аргумент: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Неверный аргумент: {str(error)}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ У вас недостаточно прав для использования этой команды.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ У бота недостаточно прав для выполнения этой команды.")
    else:
        logger.error(f"Необработанная ошибка: {error}")
        await ctx.send(f"❌ Произошла ошибка: {str(error)}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    """Обработка ошибок slash-команд."""
    try:
        # Логируем информацию о команде для отладки
        command_name = "неизвестно"
        if hasattr(interaction, 'command') and interaction.command:
            command_name = interaction.command.name
        elif hasattr(interaction, 'data') and interaction.data:
            command_name = interaction.data.get('name', 'неизвестно')
        
        guild_name = "ЛС" if not interaction.guild else interaction.guild.name
        guild_id = "ЛС" if not interaction.guild else interaction.guild.id
        user_name = f"{interaction.user} ({interaction.user.id})" if interaction.user else "Неизвестный пользователь"
        
        logger.info(f"Ошибка команды /{command_name} от {user_name} на сервере {guild_name} (ID: {guild_id})")

        # Обработка известных типов ошибок
        if isinstance(error, discord.errors.NotFound):
            logger.warning(f"Interaction not found: {error}")
            return

        if isinstance(error, discord.errors.InteractionResponded):
            logger.warning(f"Interaction already responded: {error}")
            return

        if isinstance(error, app_commands.CommandNotFound):
            logger.warning(f"Команда не найдена: /{command_name}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Команда не найдена. Пожалуйста, подождите немного или перезайдите в Discord.", ephemeral=True)
            return
        elif isinstance(error, app_commands.MissingPermissions):
            logger.warning(f"Отсутствуют права для {user_name} на использование /{command_name}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ У вас недостаточно прав для использования этой команды.", ephemeral=True)
            return
        elif isinstance(error, app_commands.BotMissingPermissions):
            logger.warning(f"Отсутствуют права у бота на выполнение /{command_name}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ У бота недостаточно прав для выполнения этой команды. Пожалуйста, проверьте права бота на сервере.", 
                    ephemeral=True
                )
            return
        elif isinstance(error, app_commands.CommandOnCooldown):
            logger.warning(f"Команда /{command_name} на перезарядке для {user_name}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"⏱️ Пожалуйста, подождите {error.retry_after:.1f} секунд перед повторным использованием этой команды.", 
                    ephemeral=True
                )
            return
        elif isinstance(error, app_commands.CheckFailure):
            logger.warning(f"Проверка не пройдена для команды /{command_name}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Вы не можете использовать эту команду в данном контексте.", 
                    ephemeral=True
                )
            return
            
        # Обработка неизвестных ошибок
        # Добавляем подробную информацию для отладки
        error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"Ошибка в slash-команде /{command_name}:\n{error_traceback}")
        
        try:
            # Пробуем переинициализировать команды после ошибки
            logger.info("Переинициализация команд после ошибки...")
            await load_cogs()
            await bot.tree.sync()
        except Exception as sync_error:
            logger.error(f"Ошибка при переинициализации команд: {sync_error}")
            
    except Exception as e:
        error_traceback = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"Критическая ошибка при обработке исключения команды:\n{error_traceback}")

    # Пытаемся отправить пользователю информативное сообщение об ошибке
    try:
        error_message = (
            f"❌ **Ошибка при выполнении команды**\n\n"
            f"Произошла непредвиденная ошибка при обработке команды. "
            f"Информация об ошибке записана в логи. "
            f"Пожалуйста, попробуйте еще раз через несколько секунд."
        )
        
        if not interaction.response.is_done():
            await interaction.response.send_message(error_message, ephemeral=True)
        else:
            await interaction.followup.send(error_message, ephemeral=True)
    except Exception as msg_error:
        logger.error(f"Не удалось отправить сообщение об ошибке: {msg_error}")
        try:
            if hasattr(interaction, 'channel') and interaction.channel:
                await interaction.channel.send(f"❌ Произошла ошибка при выполнении команды.")
        except:
            pass

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command and interaction.command is None:
        try:
            command_name = interaction.data.get('name', 'неизвестная')
            user_id = interaction.user.id if interaction.user else "Неизвестный пользователь"
            guild_id = interaction.guild.id if interaction.guild else "ЛС"
            logger.warning(f"Обнаружена ошибка 'Неизвестная интеграция' для команды: /{command_name} от пользователя {user_id} на сервере {guild_id}")
            
            # Получаем список известных команд
            known_commands = []
            for cmd in bot.tree.get_commands():
                known_commands.append(cmd.name)
            logger.info(f"Известные команды: {', '.join(known_commands)}")
            
            # Проверяем наличие модулей cog и их команд
            logger.info("Проверка загруженных cogs и их команд:")
            for cog_name, cog in bot.cogs.items():
                logger.info(f"- Cog: {cog_name}")
                if hasattr(cog, 'get_commands'):
                    for cmd in cog.get_commands():
                        logger.info(f"  - Команда: {cmd.name}")
            
            # Отправляем детальное информационное сообщение пользователю
            error_message = (
                f"⚠️ **Ошибка: Неизвестная интеграция** для команды `/{command_name}`\n\n"
                "Эта ошибка связана с обновлением кэша команд Discord.\n\n"
                "**Что делать:**\n"
                "1. Подождите 1-2 минуты и попробуйте снова\n"
                "2. Перезайдите в Discord\n"
                "3. Попробуйте другую команду, например `/помощь`\n\n"
                "Бот уже выполнил переинициализацию команд и вскоре они должны заработать."
            )
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(error_message, ephemeral=True)
                else:
                    await interaction.followup.send(error_message, ephemeral=True)
            except Exception as msg_err:
                logger.error(f"Не удалось отправить сообщение об ошибке: {msg_err}")
                # Пробуем отправить в канал, если есть доступ
                if hasattr(interaction, 'channel') and interaction.channel:
                    try:
                        await interaction.channel.send(
                            f"⚠️ {interaction.user.mention}, обнаружена ошибка 'Неизвестная интеграция' при использовании команды /{command_name}.\n"
                            f"Пожалуйста, подождите несколько минут и попробуйте снова, или перезайдите в Discord."
                        )
                    except Exception as channel_err:
                        logger.error(f"Не удалось отправить сообщение в канал: {channel_err}")
            
            # Запускаем процесс исправления в фоне
            asyncio.create_task(fix_unknown_integration(interaction))
            
        except Exception as e:
            logger.error(f"Глобальная ошибка при обработке 'Неизвестная интеграция': {e}")

async def fix_unknown_integration(interaction):
    """Функция для исправления ошибки 'Неизвестная интеграция'"""
    try:
        guild_name = interaction.guild.name if interaction.guild else "ЛС"
        guild_id = interaction.guild.id if interaction.guild else "ЛС"
        logger.info(f"Запуск процесса исправления 'Неизвестная интеграция' для сервера {guild_name} (ID: {guild_id})")
        
        # Шаг 1: Проверим и выгрузим все модули если необходимо
        for extension in list(bot.extensions.keys()):
            try:
                await bot.unload_extension(extension)
                logger.info(f"Выгружен модуль {extension}")
            except Exception as e:
                logger.error(f"Ошибка при выгрузке {extension}: {e}")
        
        # Шаг 2: Загрузим все модули заново
        await load_cogs()
        await asyncio.sleep(1)
        
        # Шаг 3: Получим список уже зарегистрированных глобальных команд
        try:
            existing_commands = await bot.http.get_global_commands(bot.user.id)
            logger.info(f"Текущий список глобальных команд: {len(existing_commands)}")
            
            # Выведем список существующих команд для диагностики
            for cmd in existing_commands:
                logger.info(f"- /{cmd['name']} (ID: {cmd['id']})")
        except Exception as e:
            logger.error(f"Ошибка при получении списка существующих команд: {e}")
        
        # Шаг 4: Синхронизируем глобальные команды
        try:
            logger.info("Синхронизация глобальных команд...")
            synced = await bot.tree.sync()
            logger.info(f"Глобальные команды синхронизированы: {len(synced)}")
            
            for cmd in synced:
                logger.info(f"- /{cmd.name}")
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit
                retry_after = e.retry_after
                logger.warning(f"Rate limit при синхронизации, ожидание {retry_after} секунд...")
                await asyncio.sleep(retry_after + 1)
                synced = await bot.tree.sync()
                logger.info(f"Глобальные команды синхронизированы после ожидания: {len(synced)}")
            else:
                logger.error(f"HTTP ошибка при синхронизации глобальных команд: {e}")
        except Exception as e:
            logger.error(f"Ошибка при синхронизации глобальных команд: {e}")
        
        # Шаг 5: Синхронизируем команды для конкретного сервера
        if interaction.guild:
            try:
                logger.info(f"Синхронизация команд для сервера {interaction.guild.name} (ID: {interaction.guild.id})...")
                guild_commands = await bot.tree.sync(guild=interaction.guild)
                logger.info(f"Команды для сервера синхронизированы: {len(guild_commands)}")
                
                for cmd in guild_commands:
                    logger.info(f"- /{cmd.name}")
            except discord.errors.HTTPException as e:
                if e.status == 429:  # Rate limit
                    retry_after = e.retry_after
                    logger.warning(f"Rate limit при синхронизации команд сервера, ожидание {retry_after} секунд...")
                    await asyncio.sleep(retry_after + 1)
                    guild_commands = await bot.tree.sync(guild=interaction.guild)
                    logger.info(f"Команды для сервера синхронизированы после ожидания: {len(guild_commands)}")
                else:
                    logger.error(f"HTTP ошибка при синхронизации команд сервера: {e}")
            except Exception as e:
                logger.error(f"Ошибка при синхронизации команд сервера: {e}")
        
        logger.info("Процесс исправления 'Неизвестная интеграция' завершен")
        
    except Exception as e:
        logger.error(f"Критическая ошибка в процессе исправления 'Неизвестная интеграция': {e}")

@bot.event
async def on_guild_join(guild):
    """Событие, срабатывающее когда бот присоединяется к новому серверу."""
    logger.info(f"Бот присоединился к серверу: {guild.name} (ID: {guild.id})")
    from models import create_default_guild_config
    
    # Создаем конфигурацию по умолчанию для нового сервера
    create_default_guild_config(guild.id)
    
    # Принудительная синхронизация команд для нового сервера
    try:
        logger.info(f"Синхронизируем команды для сервера {guild.name} (ID: {guild.id})...")
        # Проверяем, что все модули загружены
        await load_cogs()
        
        # Синхронизируем глобальные команды сначала
        await asyncio.sleep(1)
        global_commands = await bot.tree.sync()
        logger.info(f"Глобальные команды синхронизированы: {len(global_commands)}")
        
        # Затем синхронизируем команды для сервера
        guild_commands = await bot.tree.sync(guild=guild)
        logger.info(f"Синхронизация для сервера {guild.name}: {len(guild_commands)} команд")
        
        # Проверяем, успешно ли синхронизировались команды
        if not guild_commands:
            logger.warning(f"После синхронизации не найдено команд для сервера {guild.name}")
            
            # Повторная попытка с дополнительной задержкой
            await asyncio.sleep(3)
            commands = bot.tree.get_commands()
            if commands:
                logger.info(f"Команды найдены ({len(commands)}), выполняем синхронизацию для сервера...")
                guild_commands = await bot.tree.sync(guild=guild)
                logger.info(f"Повторная синхронизация для сервера {guild.name}: {len(guild_commands)} команд")
            else:
                logger.error("Команды не найдены! Невозможно выполнить синхронизацию для сервера")
                
        # Отправляем уведомление в системный канал о возможной задержке команд
        system_channel = guild.system_channel
        if system_channel and system_channel.permissions_for(guild.me).send_messages:
            try:
                await system_channel.send(
                    "⚠️ **Важное уведомление:** команды бота могут появиться с небольшой задержкой (от 1 до 5 минут). "
                    "Это связано с обновлением кэша Discord. Пожалуйста, подождите."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление о задержке команд: {e}")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации команд для нового сервера: {e}")

@bot.event
async def on_guild_available(guild):
    """Событие срабатывает когда сервер становится доступным после запуска бота."""
    logger.info(f"Сервер стал доступен: {guild.name} (ID: {guild.id})")
    try:
        # Проверяем наличие конфигурации для сервера
        from models import get_guild_config, create_default_guild_config
        config = get_guild_config(guild.id)
        if not config:
            logger.info(f"Создаем конфигурацию по умолчанию для сервера {guild.name} (ID: {guild.id})")
            create_default_guild_config(guild.id)
        
        # Синхронизируем команды для сервера
        try:
            guild_commands = bot.tree.get_commands(guild=guild)
            
            # Всегда синхронизируем команды при доступности сервера для надежности
            logger.info(f"Синхронизируем команды для сервера {guild.name} (ID: {guild.id})...")
            guild_commands = await bot.tree.sync(guild=guild)
            
            if guild_commands:
                logger.info(f"Команды для сервера {guild.name} (ID: {guild.id}) синхронизированы: {len(guild_commands)} команд")
                for cmd in guild_commands:
                    logger.info(f"  - /{cmd.name}")
            else:
                logger.warning(f"После синхронизации не найдено команд для сервера {guild.name}")
                
                # Проверяем текущее состояние
                logger.info(f"Текущее состояние бота: {len(bot.extensions)} расширений, {len(bot.cogs)} cogs")
                if len(bot.tree.get_commands()) == 0:
                    logger.warning("Не найдено ни одной слеш-команды. Выполняем полную переинициализацию...")
                    
                    try:
                        # Выполним принудительную синхронизацию глобальных команд
                        global_commands = await bot.tree.sync()
                        logger.info(f"Глобальные команды синхронизированы: {len(global_commands)}")
                        
                        # После глобальной синхронизации, пробуем server-specific команды
                        guild_commands = await bot.tree.sync(guild=guild)
                        logger.info(f"Команды для сервера {guild.name}: {len(guild_commands)}")
                        
                        if not guild_commands and not global_commands:
                            # Если ничего не помогло, пробуем перезагрузить cogs
                            logger.critical("Критическая проблема с командами! Принудительная перезагрузка cogs...")
                            
                            # Сначала выгружаем все модули
                            for extension in list(bot.extensions.keys()):
                                try:
                                    await bot.unload_extension(extension)
                                    logger.info(f"Выгружен модуль {extension}")
                                except Exception as e:
                                    logger.error(f"Ошибка при выгрузке {extension}: {e}")
                            
                            # Загружаем заново
                            await load_cogs()
                            
                            # И пробуем снова синхронизировать
                            await asyncio.sleep(1)
                            global_commands = await bot.tree.sync()
                            logger.info(f"После полной перезагрузки: {len(global_commands)} глобальных команд")
                    except Exception as critical_error:
                        logger.critical(f"Критическая ошибка синхронизации: {critical_error}")
                        error_traceback = ''.join(traceback.format_exception(type(critical_error), critical_error, critical_error.__traceback__))
                        logger.critical(f"Детали ошибки:\n{error_traceback}")
                else:
                    # Если команды уже есть, просто синхронизируем их для этого сервера
                    logger.info(f"Команды найдены ({len(bot.tree.get_commands())}), выполняем синхронизацию для сервера...")
                    guild_commands = await bot.tree.sync(guild=guild)
                    logger.info(f"Синхронизация для сервера {guild.name}: {len(guild_commands)} команд")
        
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit error
                logger.warning(f"Rate limit при синхронизации команд сервера, ожидание: {e.retry_after} секунд")
                await asyncio.sleep(e.retry_after + 1)
                guild_commands = await bot.tree.sync(guild=guild)
                logger.info(f"Команды для сервера синхронизированы после ожидания: {len(guild_commands)} команд")
            else:
                raise
                
    except Exception as e:
        logger.error(f"Ошибка при обработке доступности сервера {guild.id}: {e}")