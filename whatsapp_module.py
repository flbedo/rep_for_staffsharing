from hyperion import Hyperion
import google_sheets as gs
import telebot
from telebot import types
from whatsapp_api_client_python import API
from whatsapp_chatbot_python import GreenAPIBot, Notification
from whatsapp_chatbot_python.filters import TEXT_TYPES
import easydata3 as ed
import localcd as cd
from io import BytesIO

import requests
import easydata3 as ed
import localcd as cd
import datetime
import asyncio
import pytz
from wget import download
from pathlib import Path
import os
import bb
from config import get_config
from geo import *
from threading import Thread


whatsapp_bot = GreenAPIBot(get_config().get('whatsapp_id'),
                           get_config().get('whatsapp_token'),
                           raise_errors=True,
                           )
bot = telebot.TeleBot(get_config().get('telegram_token'))
main_chat_rus = int(get_config().get('main_chat_rus'))
main_chat_kz = int(get_config().get('main_chat_kz'))
greenAPI = API.GreenAPI(get_config().get('whatsapp_id'),
                        get_config().get('whatsapp_token'))
v_code = int(get_config().get('verification_code'))

hype = Hyperion()
google_link = get_config().get('google_link')

google_sheets_1c = gs.GoogleSheets(google_link, 'staffsharing-468818-3d25c9372397.json')

async_loop = asyncio.new_event_loop()
def run_async(coro):
    asyncio.run_coroutine_threadsafe(coro, async_loop)
def run_loop():
    asyncio.set_event_loop(async_loop)
    async_loop.run_forever()

DB_NAME = 'users'
db_path = Path(f'{DB_NAME}.db')
if not db_path.exists():
    ed.create_database(DB_NAME)
    ed.give_item_data(DB_NAME, 'system', 'max_history', 15)
    ed.give_item_data(DB_NAME, 'system', 'bot', 1)
    ed.give_item_data(DB_NAME, 'system', 'mailings_groups', '')
    ed.give_item_data(DB_NAME, 'system', 'themes', '')

CHATS = 'chats'
db_path = Path(f'{CHATS}.db')
if not db_path.exists():
    ed.create_database(CHATS)
    ed.give_item_data(CHATS, 'system', 'id', '1')
    print('Создан файл данных чатов!')

    # safe_remove(f'./{file}')


def create_account(user_id, from_app):
    user_id = str(user_id)
    if not ed.is_id_exist(DB_NAME, user_id):
        ed.give_item_data(DB_NAME, user_id, 'status', 'stable')
        ed.give_item_data(DB_NAME, user_id, 'chat_id', 0)
        ed.give_item_data(DB_NAME, user_id, 'ban', 0)
        ed.give_item_data(DB_NAME, user_id, 'from', from_app)
        ed.give_item_data(DB_NAME, user_id, 'date', 0)
        ed.give_item_data(DB_NAME, user_id, 'name', '')
        ed.give_item_data(DB_NAME, user_id, 'city', '')
        ed.give_item_data(DB_NAME, user_id, 'phone_number', 0)
        ed.give_item_data(DB_NAME, user_id, 'verify', 0)
        ed.give_item_data(DB_NAME, user_id, 'role', 'user')
        ed.give_item_data(DB_NAME, user_id, 'сash', '')


def meeting(user_id, chat_id, answer):

    if ed.get_item_data(DB_NAME, user_id, 'verify') == 2:  # 1 -> 2 город, страна
        city = hype.fast_ai('''Ты система распознавания названия города. 
                  Тебе дадут цельное или орфографически неверное написание города, 
                  а ты должна в ответет дать его верное название.
                  Ты можешь писать название города и ничего больше. 
                  Формат ответа: [Город]''', answer).replace('[', '').replace(']', '')

        if not get_country_by_city(city):
            greenAPI.sending.sendMessage(
            f"{chat_id}@c.us", 'Напиши, пожалуйста, название города правильно, иначе я не смогу помочь')
            return

        ed.give_item_data(DB_NAME, user_id, 'country',
                          get_country_by_city(city))
        ed.give_item_data(DB_NAME, user_id, 'city', city)
        greenAPI.sending.sendMessage(
            f"{chat_id}@c.us", 'Назови свое имя или ФИО')
        ed.give_item_data(DB_NAME, user_id, 'verify', 3)

    elif ed.get_item_data(DB_NAME, user_id, 'verify') == 3:
        city = ed.get_item_data(DB_NAME, user_id, 'city')
        name = ed.give_item_data(DB_NAME, user_id, 'name', answer)
        ed.give_item_data(DB_NAME, user_id, 'verify', 7)
        greenAPI.sending.sendMessage(
            f"{chat_id}@c.us", f'Я записал тебя как {name} из города {city}. Если я неверно что-то определил - обратись к оператору')
        greenAPI.sending.sendMessage(
            f"{chat_id}@c.us", 'Хорошо, сразу говорю - я бот, поэтому формулируй развернутый вопрос одной-двумя фразами, так у меня получится быстрей тебя понять')
        greenAPI.sending.sendMessage(
            f"{chat_id}@c.us", 'Слушаю твой вопрос :)')

def verification(sender_id, input_data):
    verify_level = ed.get_item_data(DB_NAME, sender_id, 'verify')
    bb.add(f'verification:{verify_level}', f'{sender_id}')

    if verify_level == 0:
        greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Привет, меня зовут Хайпи! Я бот тех. поддержки Staffsharing')
        greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Напиши свой номер телефона, под которым ты зарегистрирован в приложении')
        ed.give_item_data(DB_NAME, sender_id, 'verify', 1)
        
    elif verify_level == 1:
        
        for s in '+-()':
            input_data = input_data.replace(s, '')
        if input_data[0] == '8':
            input_data = '7' + input_data[1:]
            
        input_data = input_data.strip()
            
        if len(input_data) < 11 or not(str(input_data).isdigit()):
            greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Напиши свой номер телефона в формате 79999999999')
            return
        
        ed.give_item_data(DB_NAME, sender_id, 'phone_number', input_data)
        
        sender_line = google_sheets_1c.get_line_by_item('1С:', 'Телефон:', input_data)
        
        
        if sender_line == []:
            greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Я не нашел тебя в своей базе данных :(')
            greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Возможно, ты ввел номер телефона неправильно,\nили ты не зарегистрирован в приложении,\nили еще никогда не брал у нас велосипед в аренду')
            greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Тогда мы сделаем по-другому...')
            greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Напиши город в котором ты работаешь')
            ed.give_item_data(DB_NAME, sender_id, 'verify', 2)
            
            return
        
        name = google_sheets_1c.get_item_by_line('1С:', sender_line[0], 'ФИО:')
        city = google_sheets_1c.get_item_by_line('1С:', sender_line[0], 'Точка выдачи:').split(' - ')[0]
        country = get_country_by_city(city)
        phone_number = input_data
        
        ed.give_item_data(DB_NAME, sender_id, 'name', name)
        ed.give_item_data(DB_NAME, sender_id, 'city', city)
        ed.give_item_data(DB_NAME, sender_id, 'phone_number', phone_number)
        ed.give_item_data(DB_NAME, sender_id, 'verify', 7)
        ed.give_item_data(DB_NAME, sender_id, 'country', country)
        
        greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", f'Я записал тебя как {name} из города {city}. Если я неверно что-то определил - обратись к оператору')
        greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Хорошо, сразу говорю - я бот, поэтому формулируй развернутый вопрос одной-двумя фразами, так у меня получится быстрей тебя понять')
        greenAPI.sending.sendMessage(
            f"{sender_id}@c.us", 'Слушаю твой вопрос :)')
        
    else:
        meeting(sender_id, sender_id, input_data)

def chat_history(chat_id, user_id=0, message=0, message_type='text'):
    if user_id != 0:

        last_id = int(ed.get_item_data(CHATS, 'system', 'id'))
        ed.give_item_data(CHATS, last_id, 'user_id', user_id)
        ed.give_item_data(CHATS, last_id, 'chat_id', chat_id)
        ed.give_item_data(CHATS, last_id, 'message_type', message_type)
        ed.give_item_data(CHATS, last_id, 'time', datetime.datetime.now(
            tz=pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'))

        if message_type == 'text':
            ed.give_item_data(CHATS, last_id, 'message', message)

        elif message_type != 'text' and message:
            ed.give_item_data(CHATS, last_id, 'message', message_type)
        else:
            ed.give_item_data(CHATS, last_id, 'message',
                              '__Сообщение с файлом__')

        ed.give_item_data(CHATS, 'system', 'id', last_id+1)

    history = {}
    for id in ed.ids(CHATS):
        if ed.get_item_data(CHATS, id, 'chat_id') == chat_id:
            data = ed.get_id_data(CHATS, id)
            history[id] = {
                'user_id': data['user_id'],
                'message': data['message'],
                'message_type': data['message_type'],
                'time': data['time']
            }

        # print(history)

    return history

class SessionAgent:

    def to_session_send(self, sender_id, message: Notification):
        message_type = message.event["messageData"]["typeMessage"].replace(
            'Message', '').replace('extendedText', 'text')
        message_text = message.get_message_text()
        
        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, sender_id, 'country') == 'Россия' else main_chat_kz

        user_chat_id = int(ed.get_item_data(DB_NAME, sender_id, 'chat_id'))

        bb.add(f'to_session_send:{sender_id}', f'{message_text} | {message_type}')

        chat_history(sender_id, sender_id, message_text, message_type)
        chat_history(user_chat_id, sender_id, message_text, message_type)

        self.telegram_send_message(user_chat_id, message)
        
        if any(stop_words in message_text.lower() for stop_words in ['спасиб', 'до свидания', 'понял']):
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button1 = types.InlineKeyboardButton(
                text="✅ Согласен", callback_data=f'close:{sender_id}')

            keyboard.add(button1)
            bot.send_message(main_chat, 'Предлагаю закрыть сессию 😇', reply_markup=keyboard, message_thread_id=user_chat_id)

    def download_file(self, message: Notification):

        file = message.event["messageData"]["fileMessageData"]["downloadUrl"]
        download(file, bar=None)
        return file.split('/')[-1]

    def download_file_by_url(self, file_url):
        response = requests.get(file_url)
        response.raise_for_status()
        return BytesIO(response.content)

    def safe_remove(self, file_path, max_retries=5, delay=0.5):
        for _ in range(max_retries):
            try:
                os.remove(file_path)
                return True
            except PermissionError:
                time.sleep(delay)
        return False

    def whatsapp_send_message(self, chat_id, message: Notification):
        message_text = message.get_message_text(
        ) or message.event["messageData"]["fileMessageData"]["caption"]
        message_type = message.event["messageData"]["typeMessage"].replace(
            'Message', '').replace('extendedText', 'text')
        if message_type != 'text':
            file = self.download_file(message)
            # url = "https://1103.media.green-api.m/waInstance1103158434/sendFileByUpload/77c6e75b50224c6a989a1efb59cafe9e545f4b0be525417eb7"

            # payload = {
            # 'chatId': f'{chat_id}@c.us',
            # 'fileName': 'operator media'
            # }
            # files = [
            # ('file', (file[0], open(f'./{file[0]}','rb'),f'{file[1]}/{type}'))
            # # ('Досрочный ОГЭ 2025.pdf', open('C:/Досрочный ОГЭ 2025.pdf','rb'),'application/pdf')
            # # ('Деньги.docx', open('C:/Деньги.docx','rb'),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            # ]
            # headers= {}

            # response = requests.post(url, data=payload, files=files)

            response = greenAPI.sending.sendFileByUpload(
                f"{chat_id}@c.us",
                f"./{file}",
                file,
            )

            self.safe_remove(f'./{file}')

        if message_type == "text":

            response = greenAPI.sending.sendMessage(
                f"{chat_id}@c.us", message_text)

        return response.data

    def telegram_send_message(self, chat_id, message: Notification):

        sender_data = message.event["senderData"]
        sender_name = sender_data["senderName"]
        sender_number = sender_data["sender"]
        sender_id = int(sender_number.replace("@c.us", ""))
        message_text = message.get_message_text(
        ) or message.event["messageData"]["fileMessageData"]["caption"]
        message_type = message.event["messageData"]["typeMessage"].replace(
            'Message', '').replace('extendedText', 'text')

        if message_type != 'text':
            file_url = message.event["messageData"]["fileMessageData"]["downloadUrl"]
        else:
            file_url = None

        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, sender_id, 'country') == 'Россия' else main_chat_kz

        if message_type == "text":
            bot.send_message(
                chat_id=main_chat,
                text=message_text,
                message_thread_id=chat_id
            )
        elif message_type == "image":
            bot.send_photo(
                chat_id=main_chat,
                photo=file_url,
                caption=message_text,
                message_thread_id=chat_id
            )
        elif message_type == "video":
            bot.send_video(
                chat_id=main_chat,
                video=file_url,
                caption=message_text,
                message_thread_id=chat_id
            )
        elif message_type == "audio":
            bot.send_audio(
                chat_id=main_chat,
                audio=file_url,
                caption=message_text,
                message_thread_id=chat_id
            )
        elif message_type == "document":
            try:
                bot.send_document(
                    chat_id=main_chat,
                    document=file_url,
                    caption=message_text,
                    message_thread_id=chat_id
                )
            except:
                print(
                    'Ошибка отправки документа. Попытка отправить файл прямым запросом...', end=' ')
                response = requests.get(file_url)
                response.raise_for_status()
                file_data = BytesIO(response.content)
                bot.send_document(
                    chat_id=main_chat,
                    document=file_data,
                    caption=message_text,
                    message_thread_id=chat_id
                )
                print('Успешно!')
        else:
            message.answer('Неподдерживаемый тип файла.')
            print(message_type, message.event["messageData"]["fileMessageData"])

    def create_session(self, sender_id):
        user_id = sender_id

        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, user_id, 'country') == 'Россия' else main_chat_kz

        result = bot.create_forum_topic(
            main_chat,
            f'Nobody`s chat {user_id}'
        )

        user_chat_id = int(result.message_thread_id)
        bb.add(f'create_session:{user_id}', f'{user_chat_id}')

        ed.give_item_data(DB_NAME, user_id, 'chat_id', user_chat_id)

        history = chat_history(sender_id)

        self.send_chat_history(sender_id)

        name = ed.get_item_data(DB_NAME, user_id, 'name')
        city = ed.get_item_data(DB_NAME, user_id, 'city')
        phone_number = ed.get_item_data(DB_NAME, user_id, 'phone_number')
        bot.send_message(
            main_chat, f'Данные пользователя:\nФИО: {name}\nГород: {city}\nНомер телефона: {phone_number}\nЧат: {user_id}\nID сессии: {user_chat_id}\nМессенджер: Telegram', message_thread_id=user_chat_id)

        ed.give_item_data(DB_NAME, user_id, 'status', 'waiting')
        ed.give_item_data(DB_NAME, user_id, 'date', datetime.datetime.now(
            pytz.timezone("Europe/Moscow")).strftime('%H:%M %d.%m'))

        qa = hype.analize(history)

        keyboard = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(
            text="Поднять чат", callback_data=f'accept:{user_chat_id}')
        keyboard.add(button1)

        text = f'Поступил вызов от {sender_id}\nДля принятия, напишите в соответствующий чат. Нажатие на кнопку опционально\n\nТематика вызова: {qa[0]}'

        message = bot.send_message(main_chat, text, reply_markup=keyboard)
        message_id = message.message_id

        ed.give_item_data(DB_NAME, user_chat_id, 'author', user_id)
        ed.give_item_data(DB_NAME, user_chat_id, 'question', '')
        ed.give_item_data(DB_NAME, user_chat_id, 'answer', '')
        ed.give_item_data(DB_NAME, user_chat_id, 'notification', message_id)
        ed.give_item_data(DB_NAME, user_chat_id, 'operator', 0)

        if self.get_old_session(user_id, user_chat_id, False):
            keyboard = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(
                text="Просмотреть", callback_data=f'get_old:{user_chat_id}')
            keyboard.add(button1)
            message = bot.send_message(main_chat, 'Найдена активная сессия старой версии!',
                                    reply_markup=keyboard, message_thread_id=user_chat_id)

        return user_chat_id

    def get_old_session(self, client, session_id, need_chat=True):

        if ed.get_item_data('support', client, 'status') != 'session':
            return False
        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, client, 'country') == 'Россия' else main_chat_kz

        user_chat_id = ed.get_item_data('support', client, 'chat_id')

        if need_chat:
            history = ed.get_item_data(
                'support', user_chat_id, 'history').split('➤')
            chat = ''
            blocks = []

            for msg in history:
                if msg.startswith('op:'):
                    msg = msg.replace('op:', '')
                    chat += f'Оператор:\n{msg}\n\n'
                elif msg.startswith('client:'):
                    msg = msg.replace('client:', '')
                    chat += f'Клиент:\n{msg}\n\n'

            block_count = len(chat) // 4000 + 1

            for n in range(block_count):
                block = chat[(n)*4000:min((n+1)*4000, len(chat))]
                blocks.append(block)

            for block in blocks:
                bot.send_message(main_chat, block, message_thread_id=session_id)

            bot.send_message(main_chat, f'Конец старой сессии',
                            message_thread_id=session_id)

            bb.add(f'get_old_session:{session_id}', f'{client}')
            # ed.give_item_data('support', client, 'status', 'stable')

        return True

    def send_chat_history(self, sender_id):
        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, sender_id, 'country') == 'Россия' else main_chat_kz

        user_chat_id = ed.get_item_data(DB_NAME, sender_id, 'chat_id')

        history = chat_history(sender_id)

        max_history = int(ed.get_item_data(DB_NAME, 'system', 'max_history'))

        out_text = ''
        blocks = []

        for msg in sorted(history.keys(), key=int)[-1 * max_history:]:
            author = history[msg]['user_id']
            text = history[msg]['message']
            out_text += f'{author} #{msg}\n{text}\n\n'

        block_count = len(out_text) // 4000 + 1

        for n in range(block_count):
            block = out_text[n*4000:min((n+1)*4000, len(out_text))]
            blocks.append(block)

        for block in blocks:
            bot.send_message(main_chat, block, message_thread_id=user_chat_id)

@whatsapp_bot.router.message()
def handler(notification: Notification):
    run_async(async_handler(notification))
    
async def async_handler(notification: Notification):
    sender_data = notification.event["senderData"]
    sender_name = sender_data["senderName"]
    sender_number = sender_data["sender"]
    sender_id = int(sender_number.replace("@c.us", ""))
    message_text = notification.get_message_text(
    ) or notification.event["messageData"]["fileMessageData"]["caption"]
    message_type = notification.event["messageData"]["typeMessage"].replace(
        'Message', '').replace('extendedText', 'text')

    session = SessionAgent()

    if str(sender_id) == '79912860443': return

    bb.add(
        f'{sender_id}.Private | {sender_id}',
        f'{message_text} | {message_type}',
    )

    create_account(sender_id, 'whatsapp')

    if ed.get_item_data(DB_NAME, sender_id, 'ban') == 2:
        notification.answer(
            ('Извини, ты был заблокирован оператором. Ты не можешь общаться с ботом.'))
        return

    chat_history(sender_id, sender_id, message_text, message_type)

    if cd.cooldown_check(sender_id, 'question_ai', 35):
        left = cd.cooldown_check(sender_id, 'question_ai', 35)['seconds']
        notification.answer(
            (f'Я ищу ответ на твой прошлый вопрос, пожалуйста подожди......\nВернусь через {time} секунд'))
        return

    if ed.get_item_data(DB_NAME, sender_id, 'status') in ['session', 'waiting']:
        session.to_session_send(sender_id, notification)
        cd.cooldown_set(sender_id, 'question_op')
        return

    if ed.get_item_data(DB_NAME, sender_id, 'verify') < v_code:  # знакомство
        verification(sender_id, message_text)
        return

    cd.cooldown_set(sender_id, 'question_ai')
    answer = await hype.ai_response(
        message_text, sender_id) if message_type == 'text' else 'К сожалению я не имею работать с файлами :('
    cd.cooldown_drop(sender_id, 'question_ai')

    chat_history(sender_id, 'BOT', answer)

    if '/operator' in answer.lower().strip().replace('.', ''):
        if ed.get_item_data(DB_NAME, sender_id, 'ban') == 1:
            notification.answer(
                ('Извини, ты был заблокирован оператором. Ты не можешь его вызвать'))
            return
        session.create_session(sender_id)
        if datetime.datetime.now().weekday() in {5, 6}:
            answer = 'Я позвал оператора, но к сожалению, в настоящий момент оператор не может ответить тебе :( \nОператор ответит вам в понедельник с 10:00 до 19:00 по МСК. Желаем Вам хороших выходных!'
        elif (
            datetime.datetime.now().hour < 10
            or datetime.datetime.now().hour >= 19
        ) and datetime.datetime.now().weekday() not in {5, 6}:
            answer = 'Я позвал оператора! Твои сообщения уже транслируются. Ответ оператора последует в рабочий день с 10.00 до 19.00'
        else:
            answer = 'Я позвал оператора! Твои сообщения уже транслируются. Ожидай ответ оператора'
            # answer = 'К сожалению, оператор пока недоступен из WhatsApp. Напиши в Telegram @Staffsharing_support'

    notification.answer((answer))


async def start_whatsapp_bot():
    Thread(target=run_loop, daemon=True).start()
    while True:
        print('WhatsApp Bot запущен')
        try:
            whatsapp_bot.run_forever()
        except Exception as e:
            bb.add('whatsapp', f'Error: {e}')


if __name__ == '__main__':
    asyncio.run(start_whatsapp_bot())
