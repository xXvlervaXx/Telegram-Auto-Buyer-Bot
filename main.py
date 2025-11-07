import asyncio
import configparser
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.functions.channels import CreateChannelRequest
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

# --- ЧТЕНИЕ КОНФИГУРАЦИИ ---
config = configparser.ConfigParser()
config.read('config.ini')

# --- КОНФИГУРАЦИЯ (ИЗ ФАЙЛА) ---
API_ID = config.getint('telegram', 'api_id')
API_HASH = config.get('telegram', 'api_hash')
SESSION_NAME = config.get('telegram', 'session_name', fallback='buyer_session')

# --- НАСТРОЙКИ МОНИТОРИНГА ---
TARGET_BOT = config.get('settings', 'target_bot', fallback='globalbakery_bot')
POLLING_INTERVAL_SECONDS = config.getint('settings', 'polling_interval_seconds', fallback=60)
LOG_CHANNEL_NAME = config.get('settings', 'log_channel_name', fallback='Bakery Bot Logs')

# Callback-данные для кнопки категории
CATEGORY_CALLBACK_DATA = config.get('settings', 'category_callback_data').encode()

# Список игнорируемых коллбэков
ignore_list_str = config.get('settings', 'ignore_callbacks').split(',')
IGNORE_CALLBACKS = {s.strip().encode() for s in ignore_list_str}
IGNORE_CALLBACKS.add(CATEGORY_CALLBACK_DATA) # Всегда игнорируем саму категорию

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
main_menu_message_id = None
is_purchasing = False
log_chat_entity = None
seen_callbacks = set()

# (Здесь идет остальной код без изменений: polling_loop, product_scanner, find_and_click_action_button, initiate_purchase, setup_initial_state, setup_log_channel)
# ...
# Копируем сюда весь код функций из предыдущего ответа, он остается таким же.
# ...

async def main():
    """Основная функция."""
    # Проверка наличия конфига
    if not API_ID or not API_HASH:
        print("Ошибка: Пожалуйста, создайте файл 'config.ini' из 'config.ini.example' и заполните api_id и api_hash.")
        return

    await client.start()
    print("Клиент успешно запущен.")
    
    await setup_log_channel()
    await client.send_message(log_chat_entity, f"🚀 **Скрипт запущен!**\nНачинаю мониторинг бота @{TARGET_BOT}")
    
    await setup_initial_state()
    asyncio.create_task(polling_loop())
    
    print("--- Мониторинг запущен. Ожидаю обновлений... ---")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена вручную.")

# ВАЖНО: Весь код функций, который был между #---ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ--- и async def main(),
# нужно вставить в середину этого скрипта. Я его опустил для краткости, он не меняется.