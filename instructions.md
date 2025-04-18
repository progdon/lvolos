# Инструкция по решению ошибки "Неизвестная интеграция" в Discord боте

## Что такое ошибка "Неизвестная интеграция"?

Эта ошибка возникает, когда Discord не может найти или распознать команду бота. Обычно это происходит по следующим причинам:

1. Кэш команд Discord не обновился
2. Проблемы с регистрацией команд
3. Задержка синхронизации на стороне Discord API

## Решение для пользователей

Если вы видите ошибку "Неизвестная интеграция" при использовании команд бота:

1. **Подождите несколько минут (1-5)** - часто проблема решается автоматически
2. **Перезапустите клиент Discord** - полностью закройте и снова откройте Discord
3. **Попробуйте другую команду**, например `/помощь` - иногда это помогает "пробудить" остальные команды
4. **Проверьте права бота** - убедитесь, что у бота есть все необходимые права
5. **Выйдите и снова войдите на сервер** - это может помочь обновить кэш команд

## Радикальное решение

Если проблема сохраняется на протяжении длительного времени (более 30 минут):

1. Удалите бота с сервера
2. Подождите 5 минут
3. Добавьте бота снова, используя тот же пригласительный URL

## Для владельцев бота (как полностью исправить проблему)

Если вы владелец бота и хотите полностью исправить проблему, выполните следующие шаги:

1. Запустите скрипт `fix_unknown_integration.py` для удаления и пересоздания всех команд:
```
python fix_unknown_integration.py
```

2. После выполнения скрипта перезапустите основного бота:
```
python main.py
```

3. Дождитесь полной синхронизации команд (обычно занимает 2-3 минуты)

4. Если проблема сохраняется, попробуйте внести временные изменения в имена команд 
(например, добавить цифру в конец `/ранг1`), затем синхронизировать и вернуть обратно оригинальные имена.

## Техническая информация

В коде бота уже реализована автоматическая обработка этой ошибки:

1. При возникновении ошибки бот перезагружает все модули
2. Выполняет принудительную синхронизацию команд с Discord API
3. Отправляет информационное сообщение пользователю с указаниями
4. Запускает фоновый процесс для полного исправления проблемы

Вы всегда можете проверить статус регистрации команд в логах бота.
