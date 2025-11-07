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
API_ID = config.getint('telegram', 'api_id', fallback=0)
API_HASH = config.get('telegram', 'api_hash', fallback=None)
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

async def polling_loop():
    """Бесконечный цикл опроса категории."""
    while True:
        await asyncio.sleep(POLLING_INTERVAL_SECONDS)
        if is_purchasing or not main_menu_message_id:
            continue
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Опрашиваю категорию...")
            await client(GetBotCallbackAnswerRequest(
                peer=TARGET_BOT, msg_id=main_menu_message_id, data=CATEGORY_CALLBACK_DATA
            ))
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при опросе: {e}")
            await setup_initial_state()

@client.on(events.MessageEdited(chats=TARGET_BOT))
async def product_scanner(event):
    """Ловит обновления и ищет в них кнопки товаров."""
    if event.message.id != main_menu_message_id or is_purchasing:
        return

    if not event.message.reply_markup:
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Сообщение обновлено. Сканирую на наличие товаров...")
    
    product_to_buy = None
    for row in event.message.reply_markup.rows:
        for button in row.buttons:
            if button.data not in IGNORE_CALLBACKS:
                if not product_to_buy:
                    product_to_buy = button

                if button.data not in seen_callbacks:
                    seen_callbacks.add(button.data)
                    log_message = (
                        f"🔍 **Обнаружен новый коллбэк!**\n\n"
                        f"**Текст:** `{button.text}`\n"
                        f"**Callback Data:** `{button.data.decode('utf-8')}`"
                    )
                    await client.send_message(log_chat_entity, log_message)
    
    if product_to_buy:
        asyncio.create_task(initiate_purchase(event, product_to_buy))

async def find_and_click_action_button(event, step_name):
    """Находит первую 'неигнорируемую' кнопку и нажимает на нее."""
    print(f"-> ШАГ [{step_name}]: Ищу кнопку действия...")
    if not event.message.reply_markup:
        raise ValueError(f"На шаге '{step_name}' нет кнопок.")

    for row in event.message.reply_markup.rows:
        for button in row.buttons:
            if button.data not in IGNORE_CALLBACKS:
                button_text = button.text
                print(f"   ...найдена кнопка '{button_text}'. Нажимаю...")
                next_event = await event.click(data=button.data, wait_for=events.MessageEdited)
                print(f"   ...кнопка '{button_text}' нажата.")
                return next_event

    raise RuntimeError(f"Не удалось найти кнопку действия на шаге '{step_name}'.")

async def initiate_purchase(event, product_button):
    """Полная последовательность покупки 'вслепую'."""
    global is_purchasing
    if is_purchasing: return
    is_purchasing = True
    
    product_name = product_button.text
    product_callback = product_button.data.decode('utf-8')
    
    print(f"\n!!! ОБНАРУЖЕН ТОВАР: '{product_name}'. НАЧИНАЮ ПОКУПКУ !!!")
    await client.send_message(log_chat_entity, f"▶️ **Начинаю покупку!**\n\n**Товар:** `{product_name}`")

    try:
        event_after_product_click = await event.click(data=product_button.data, wait_for=events.MessageEdited)
        event_after_buy_click = await find_and_click_action_button(event_after_product_click, "КУПИТЬ")
        await find_and_click_action_button(event_after_buy_click, "ПОДТВЕРДИТЬ")
        
        success_message = (
            f"✅ **УСПЕШНАЯ ПОКУПКА!**\n\n"
            f"**Товар:** `{product_name}`\n"
            f"**Callback:** `{product_callback}`"
        )
        await client.send_message(log_chat_entity, success_message)
        print(f"\n✅✅✅ УСПЕХ! Покупка '{product_name}' завершена! ✅✅✅\n")

    except Exception as e:
        error_message = (
            f"❌ **ОШИБКА ПОКУПКИ!**\n\n"
            f"**Товар:** `{product_name}`\n"
            f"**Ошибка:** `{str(e)}`"
        )
        await client.send_message(log_chat_entity, error_message)
        print(f"\n❌ ОШИБКА в процессе покупки '{product_name}': {e}\n")
    finally:
        print("--- Сброс состояния для продолжения мониторинга ---\n")
        is_purchasing = False
        await setup_initial_state()

async def setup_initial_state():
    """Получает свежее сообщение с меню для работы."""
    global main_menu_message_id
    print("Настраиваю начальное состояние (отправляю /start)...")
    try:
        await client.send_message(TARGET_BOT, '/start')
        await asyncio.sleep(3)
        last_message = (await client.get_messages(TARGET_BOT, limit=1))[0]
        main_menu_message_id = last_message.id
        print(f"Начальное состояние настроено. Работаем с сообщением ID: {main_menu_message_id}")
    except Exception as e:
        print(f"Критическая ошибка при настройке состояния: {e}")
        main_menu_message_id = None

async def setup_log_channel():
    """Ищет или создает приватный канал для логов."""
    global log_chat_entity
    print(f"Поиск лог-канала '{LOG_CHANNEL_NAME}'...")
    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_channel and dialog.title == LOG_CHANNEL_NAME:
                print("Лог-канал найден.")
                log_chat_entity = dialog.entity
                return

        print("Лог-канал не найден. Создаю новый...")
        created_channel = await client(CreateChannelRequest(
            title=LOG_CHANNEL_NAME,
            about="Логи для бота-покупателя",
            megagroup=False
        ))
        log_chat_entity = created_channel.chats[0]
        print("Лог-канал успешно создан.")
    except Exception as e:
        print(f"Критическая ошибка при настройке лог-канала: {e}")
        print("Логирование будет отключено.")


async def main():
    """Основная функция."""
    if not API_ID or not API_HASH:
        print("Ошибка: Пожалуйста, создайте файл 'config.ini' из 'config.ini.example' и заполните api_id и api_hash.")
        return

    await client.start()
    print("Клиент успешно запущен.")
    
    await setup_log_channel()
    if log_chat_entity:
        await client.send_message(log_chat_entity, f"🚀 **Скрипт запущен!**\nНачинаю мониторинг бота @{TARGET_BOT}")
    
    await setup_initial_state()
    asyncio.create_task(polling_loop())
    
    print("--- Мониторинг запущен. Ожидаю обновлений... ---")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (TypeError, ValueError) as e:
        # Эта ошибка часто возникает, если config.ini заполнен неправильно
        print(f"\nОШИБКА КОНФИГУРАЦИИ: {e}")
        print("Пожалуйста, проверьте, что в файле 'config.ini' все значения (особенно api_id) заполнены корректно и не содержат лишних символов.")
    except KeyboardInterrupt:
        print("\nПрограмма остановлена вручную.")
