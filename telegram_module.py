import telebot
from telebot import types
# from torch import resize_as_sparse_
# from xgboost import DMatrix
from whatsapp_api_client_python import API
from time import sleep
# import hyperion_model as hm
from hyperion import Hyperion
import requests
import easydata3 as ed
import google_sheets as gs
import localcd as cd
import datetime
import asyncio
import pytz
import os
from xgb import ConsultationTester
from uuid import *
from pathlib import Path
# import hype_finder
# import tracemalloc
from fnmatch import fnmatch
import bb
from config import get_config
from geo import *
import re
# import json
from threading import Thread, Event
# import async_runner

import staffsharing

bot = telebot.TeleBot(get_config().get('telegram_token'),  # да, я знаю, что это не тру и что есть .yaml файлы
                      exception_handler=None)
main_chat_rus = int(get_config().get('main_chat_rus'))
main_chat_kz = int(get_config().get('main_chat_kz'))
greenAPI = API.GreenAPI(get_config().get('whatsapp_id'),
                        get_config().get('whatsapp_token')) 
v_code = int(get_config().get('verification_code')) 
google_link = get_config().get('google_link')

google_sheets_1c = gs.GoogleSheets(google_link, 'staffsharing-468818-3d25c9372397.json')
request_gh = staffsharing.RequestsGH()
session_ia = staffsharing.SessionIntentAnalyzer()
consultation_tester = ConsultationTester()

class AsyncRunner:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.stop_event = Event()
        
    def run_async(self, coro):
        # print(f'Вызвана асинхронная функция {coro}')
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        future.add_done_callback(self._handle_result)
        return future
        
    def _handle_result(self, future):
        # try:
        future.result()
        # except Exception as e:
        #     print(f"Error in async task: {e}")
            
    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()
            
    def start(self):
        self.thread = Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

async_runner = AsyncRunner()

def run_async(coro):
    return async_runner.run_async(coro)


DB_NAME = 'users'
db_path = Path(f'{DB_NAME}.db')
if not db_path.exists():
    ed.create_database(DB_NAME)
    ed.give_item_data(DB_NAME, 'system', 'max_history', 15)
    ed.give_item_data(DB_NAME, 'system', 'bot', 1)
    ed.give_item_data(DB_NAME, 'system', 'mailings_groups', '')
    ed.give_item_data(DB_NAME, 'system', 'themes', '')
    ed.give_item_data(DB_NAME, 'system', 'analize', 1)
    print('Создан файл данных пользователей!')

CHATS = 'chats'
db_path = Path(f'{CHATS}.db')
if not db_path.exists():
    ed.create_database(CHATS)
    ed.give_item_data(CHATS, 'system', 'id', '1')
    print('Создан файл данных чатов!')

hype = Hyperion()

def get_account(user_id, from_app):
    user_id = str(user_id)
    user_data = ed.get_id_data(DB_NAME, user_id)
    start_data = {
        'status': 'stable',
        'chat_id': 0,
        'ban': 0,
        'from': from_app,
        'date': 0,
        'name': '',
        'city': '',
        'phone_number': 0,
        'verify': 0,
        'role': 'user',
        'cash': '',
        'country': ''
    }
    if not user_data:
        ed.give_id_data(DB_NAME, user_id, start_data)
        user_data = start_data
    elif len(user_data.keys()) != len(start_data.keys()):
        start_data = {
            'status': 'stable',
            'chat_id': user_data['chat_id'],
            'ban': 0,
            'from': from_app,
            'date': 0,
            'name': user_data['name'],
            'city': '',
            'phone_number': 0,
            'verify': 0,
            'role': 'user',
            'cash': '',
            'country': ''
        }
        ed.give_id_data(DB_NAME, user_id, start_data)
        user_data = start_data
        
    return user_data
    
def meeting(user_id, chat_id, answer):

    if ed.get_item_data(DB_NAME, user_id, 'verify') == 2:  # 1 -> 2 город, страна
        # city = run_async(hype.fast_ai('''Ты система распознавания названия города. 
        #           Тебе дадут цельное или орфографически неверное написание города, 
        #           а ты должна в ответет дать его верное название.
        #           Ты можешь писать название города и ничего больше. 
        #           Формат ответа: [Город]''', answer))
        # print(f'Тип city = {type(city)}')
        
        city = hype.llm.generate(answer, '', system_prompt='''Ты система распознавания названия города. 
                  Тебе дадут цельное или орфографически неверное написание города, 
                  а ты должна в ответет дать его верное название.
                  Ты можешь писать название города и ничего больше. 
                  Формат ответа: [Город]''')
        
        # try:
        #     сity = city.result(timeout=10.0)  # Ждем до 10 секунд
        #     print(f"Результат: {city}")
        # except TimeoutError:
        #     print("Операция не завершилась в течение 10 секунд")
        #     сity = city.result()  # Ждем до 10 секунд
        #     print(f"Результат: {city}")
        # except Exception as e:
        #     print(f"Ошибка при выполнении: {e}")
        
        city = city.replace('[', '').replace(']', '')


        if not get_country_by_city(city) or not city:
            bot.send_message(
                chat_id, 'Напиши, пожалуйста, название города правильно, иначе я не смогу помочь')
            return

        ed.give_item_data(DB_NAME, user_id, 'country',
                          get_country_by_city(city))
        ed.give_item_data(DB_NAME, user_id, 'city', city)
        bot.send_message(chat_id, 'Назови свое имя или ФИО')
        ed.give_item_data(DB_NAME, user_id, 'verify', 3)

    elif ed.get_item_data(DB_NAME, user_id, 'verify') == 3:
        name = ed.give_item_data(DB_NAME, user_id, 'name', answer)
        city = ed.get_item_data(DB_NAME, user_id, 'city')
        ed.give_item_data(DB_NAME, user_id, 'verify', 7)
        bot.send_message(
            chat_id, f'Я записал тебя как {name} из города {city}. Если я неверно что-то определил - обратись к оператору')
        bot.send_message(
            chat_id, 'Хорошо, сразу говорю - я бот, поэтому формулируй развернутый вопрос одной-двумя фразами, так у меня получится быстрей тебя понять')
        bot.send_message(chat_id, 'Слушаю твой вопрос :)')

def verification(sender_id, input_data):
    verify_level = ed.get_item_data(DB_NAME, sender_id, 'verify')
    bb.add(f'verification:{verify_level}', f'{sender_id}')

    if verify_level == 0:
        bot.send_message(
                sender_id, 'Привет, меня зовут Хайпи! Я бот тех. поддержки Staffsharing')
        bot.send_message(
                sender_id, 'Напиши свой номер телефона, под которым ты зарегистрирован в приложении')
        ed.give_item_data(DB_NAME, sender_id, 'verify', 1)
        
    elif verify_level == 1:
        
        for s in '+-()':
            input_data = input_data.replace(s, '')
        if input_data[0] == '8':
            input_data = '7' + input_data[1:]
            
        input_data = input_data.strip()
            
        if len(input_data) < 11 or not(str(input_data).isdigit()):
            bot.send_message(sender_id, 
                             'Напиши свой номер телефона в формате 79999999999')
            return
        
        ed.give_item_data(DB_NAME, sender_id, 'phone_number', input_data)
        
        sender_line = google_sheets_1c.get_line_by_item('1С:', 'Телефон:', input_data)
        
        
        if sender_line == []:
            bot.send_message(sender_id, 
                            'Я не нашел тебя в своей базе данных :(')
            bot.send_message(sender_id, 
                            'Возможно, ты ввел номер телефона неправильно,\nили ты не зарегистрирован в приложении,\nили еще никогда не брал у нас велосипед в аренду')
            bot.send_message(sender_id, 
                            'Тогда мы сделаем по-другому...')
            bot.send_message(sender_id, 
                            'Напиши город в котором ты работаешь')
            ed.give_item_data(DB_NAME, sender_id, 'verify', 2)
            
            return
        
        name = google_sheets_1c.get_item_by_line('1С:', sender_line[0], 'ФИО:')
        city = google_sheets_1c.get_item_by_line('1С:', sender_line[0], 'Точка выдачи:').split(' - ')[0]
        country = get_country_by_city(city)
        phone_number = input_data
        
        user_data = ed.get_id_data(DB_NAME, sender_id)
        user_data['name'] = name
        user_data['city'] = city
        user_data['phone_number'] = phone_number
        user_data['verify'] = 7
        user_data['country'] = country
        
        ed.give_id_data(DB_NAME, sender_id, user_data)
                
        bot.send_message(sender_id, 
                            f'Я записал тебя как {name} из города {city}. Если я неверно что-то определил - обратись к оператору')
        bot.send_message(
            sender_id, 'Хорошо, сразу говорю - я бот, поэтому формулируй развернутый вопрос одной-двумя фразами, так у меня получится быстрей тебя понять')
        bot.send_message(sender_id, 'Слушаю твой вопрос :)')
        
    else:
        meeting(sender_id, sender_id, input_data)

def chat_history_old(chat_id, user_id=0, message=0, message_type='text'):
    if user_id != 0: # есть информация по отправителю - делаем запись

        last_id = int(ed.get_item_data(CHATS, 'system', 'id'))
        last_id_data = {
            'user_id': user_id,
            "chat_id": chat_id,
            "message_type": message_type,
            'time': datetime.datetime.now(tz=pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S')
        }
        ed.give_id_data(CHATS, last_id, last_id_data)

        if message_type == 'text':
            ed.give_item_data(CHATS, last_id, 'message', message)
        elif message_type != 'text' and message:
            ed.give_item_data(CHATS, last_id, 'message', message)
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

def chat_history(chat_id, user_id=0, message=0, message_type='text'):
    if user_id != 0: # есть информация по отправителю - делаем запись

        last_id = int(ed.get_item_data(CHATS, 'system', 'id'))
        last_id_data = {
            'user_id': user_id,
            "chat_id": chat_id,
            "message_type": message_type,
            'time': datetime.datetime.now(tz=pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S')
        }
        ed.give_id_data(CHATS, last_id, last_id_data)

        if message_type == 'text':
            ed.give_item_data(CHATS, last_id, 'message', message)
        elif message_type != 'text' and message:
            ed.give_item_data(CHATS, last_id, 'message', message)
        else:
            ed.give_item_data(CHATS, last_id, 'message',
                              '__Сообщение с файлом__')

        ed.give_item_data(CHATS, 'system', 'id', last_id+1)

    history = ed.get_ids_by_item('chats', 'chat_id', str(chat_id))

    return history

@bot.message_handler(commands=["root"])
def root(message):
    sender_id = int(message.from_user.id)
    arguments = [arg for arg in message.text.split()[1:]]
    role = ed.get_item_data(DB_NAME, sender_id, 'role')
    if len(arguments) < 3:
        bot.send_message(sender_id, f'Нехватка аргументов:\nНужны данные в формате ID ITEM NEED_DATA')
    if role == 'admin':
        id = arguments[0]
        item = arguments[1]
        data = arguments[2].replace('_', ' ')
        flags = ['-c' in arguments[3:], '-a' in arguments[3:]]
        if not ed.is_item_exist(DB_NAME, id, item) and not flags[0]:
            bot.send_message(sender_id, f'Данные не обнаружены')
            return
        if flags[1]:
            id = 'ALL'
            ed.give_all_item_data(DB_NAME, item, data)
            return
        ed.give_item_data(DB_NAME, id, item, data)
        bot.send_message(sender_id, f'Протокол прошел успешно!\nID: {id}\nITEM: {item}\nDATA: {data}')
    else:
        bot.send_message(sender_id, f'Нехватка прав доступа!')

@bot.message_handler(content_types=['new_chat_members'])
def send_group_id(message: types.Message):
    bot_obj = bot.get_me()
    bot_id = bot_obj.id
    
    for chat_member in message.new_chat_members:
        if chat_member.id == bot_id:
            bot.send_message(message.chat.id, 
                            f"Привет, меня зовут Хайпи!\n\nВот ваш номер сотрудничества с HypeSupport: \n{message.chat.id}")

class Panel:
    def __init__(self, bot):
        self.session_agent = SessionAgent()
        self.mailings_agent = MailingsAgent()
        
    @bot.message_handler(commands=["panel"])
    def panel(message):
        sender_id = int(message.from_user.id)
        chat_id = message.chat.id
        cash = ed.get_item_data(DB_NAME, str(sender_id), 'cash')
        role = ed.get_item_data(DB_NAME, str(sender_id), 'role')

        if role == 'admin':

            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button1 = types.InlineKeyboardButton(
                text="✉️ Создать рассылку", callback_data=f'panel1')
            button6 = types.InlineKeyboardButton(
                text="📚 Получить базу знаний ✖️", callback_data=f'panel6')
            button7 = types.InlineKeyboardButton(
                text="📚 Загрузить базу знаний ✖️", callback_data=f'panel7')
            button8 = types.InlineKeyboardButton(
                text="📊 Получить статистику", callback_data=f'panel8')
            button9 = types.InlineKeyboardButton(
                text="🗑️ Сбросить данные пользователя", callback_data=f'panel9')
            button10 = types.InlineKeyboardButton(
                text="📫 Работа с сессиями", callback_data=f'panel10')
            button11 = types.InlineKeyboardButton(
                text="📝 Добавить QA пару ✖️", callback_data=f'panel11')
            button12 = types.InlineKeyboardButton(
                text="📝 Автоматически обновить базу ✖️", callback_data=f'panel12')
            button13 = types.InlineKeyboardButton(
                text="👑 Выдать роль", callback_data=f'panel13')
            button14 = types.InlineKeyboardButton(
                text="🟢 Включить бота", callback_data=f'panel14')
            button15 = types.InlineKeyboardButton(
                text="🔴 Выключить бота", callback_data=f'panel15')
            button16 = types.InlineKeyboardButton(
                text="🔨 Блокировка", callback_data=f'panel16')
            button17 = types.InlineKeyboardButton(
                text="🔎 Отлов по ключевым словам ✖️", callback_data=f'panel17')
            button18 = types.InlineKeyboardButton(
                text="🗃️ Запрос данных", callback_data=f'panel18')

            keyboard.add(button1, button18, button8,
                        button9, button10, button13, button14, button15, button16)

        elif role == 'operator':

            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button1 = types.InlineKeyboardButton(
                text="✉️ Создать рассылку", callback_data=f'panel1')
            button2 = types.InlineKeyboardButton(
                text="🗃️ Запрос данных", callback_data=f'panel18')
            button9 = types.InlineKeyboardButton(
                text="🗑️ Сбросить данные пользователя ", callback_data=f'panel9')
            button10 = types.InlineKeyboardButton(
                text="📫 Работа с сессиями", callback_data=f'panel10')
            button16 = types.InlineKeyboardButton(
                text="🔨 Блокировка", callback_data=f'panel16')

            keyboard.add(button1, button2, button9, button10, button16)

        elif role == 'user':
            keyboard = types.InlineKeyboardMarkup(row_width=1)

        text = f'''

        --- Панель управления ---                  

        - Пользователь: {sender_id}            

        - Роль: {role}                     

        '''

        bot.send_message(message.chat.id, text, reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: True)
    def callback_inline(call):

        bb.add(f'callback_inline:{call.from_user.id}', f'{call.data}')
        process = Panel(bot)
        session = SessionAgent()

        if call.message:
            main_chat = call.message.chat.id
            if call.data.startswith('accept'):
                sender_id = call.from_user.id
                user_chat_id = call.data.split(':')[1]
                operator = call.from_user.first_name
                # session.accept_session(sender_id, user_chat_id)
                bot.send_message(
                    main_chat, f'{operator}, я поднял чат вверх!', message_thread_id=user_chat_id)
            if call.data.startswith('cancel'):
                user_chat_id = call.data.split(':')[1]
                ed.give_item_data(DB_NAME, user_chat_id, 'question', '')
                ed.give_item_data(DB_NAME, user_chat_id, 'answer', '')
                bot.send_message(main_chat, 'Спасибо за вашу работу! :)',
                                message_thread_id=user_chat_id)
                bot.delete_forum_topic(main_chat, user_chat_id)
            if call.data.startswith('again'):
                user_chat_id = call.data.split(':')[1]
                history = chat_history(int(user_chat_id))

                qa = hype.analize(history)

                ed.give_item_data(DB_NAME, user_chat_id, 'question', qa[0])
                ed.give_item_data(DB_NAME, user_chat_id, 'answer', qa[1])

                keyboard = types.InlineKeyboardMarkup()
                button1 = types.InlineKeyboardButton(
                    text="Подтвердить", callback_data=f'confirm:{user_chat_id}')
                button2 = types.InlineKeyboardButton(
                    text="Повторный анализ", callback_data=f'again:{user_chat_id}')
                button3 = types.InlineKeyboardButton(
                    text="Пропустить", callback_data=f'cancel:{user_chat_id}')
                keyboard.add(button1)
                keyboard.add(button2)
                keyboard.add(button3)

                text = f'''
                Пожалуйста, проверьте анализ чата!
                Вопрос:
                {qa[0]}

                Ответ:
                {qa[1]}
                '''
                bot.send_message(
                    main_chat, text, message_thread_id=user_chat_id, reply_markup=keyboard)
            if call.data.startswith('confirm'):
                user_chat_id = call.data.split(':')[1]
                bot.send_message(main_chat, 'Спасибо за вашу работу! :)',
                                message_thread_id=user_chat_id)
                bot.delete_forum_topic(main_chat, user_chat_id)
            if call.data.startswith('add_to_faq'):
                message_id = int(call.data.split(':')[1])
                q = ed.get_item_data('ai', message_id, 'contain')
                a = ed.get_item_data('ai', message_id, 'response')
                id = int(ed.get_item_data('faq', 'system', 'last_id')) + 1
                ed.give_item_data('faq', id, 'question', q)
                ed.give_item_data('faq', id, 'answer', a)
                print(f'Добавлено в FAQ #{message_id}:\n{q}\n\n{a}')
                ed.give_item_data('faq', 'system', 'last_id', id)
            if call.data.startswith('need_session'):
                sender_id = call.from_user.id
                session.create_session(sender_id)
            if call.data.startswith('end_session'):
                user_id = call.data.split(':')[1]
                session.close_session(user_id)
            if call.data.startswith('consultation'):
                query_id = call.data.split(':')[1]
                sender_id = call.from_user.id
                query_text = ed.get_item_data(CHATS, query_id, "message")
                ed.give_item_data(DB_NAME, sender_id, 'cash', query_text)
                
                msg = bot.send_message(sender_id, 'Жду ответ на вопрос клиента...')
                
                bot.register_next_step_handler(msg, process.consultation)


            if call.data.split(':')[0] == 'panel1':
                sender_id = call.from_user.id

                cash = ed.get_item_data(DB_NAME, sender_id, 'cash')

                if len(call.data.split(':')) == 3: # Работа с группами
                    group_action = call.data.split(':')[2]

                    if group_action == 'create':
                        msg = bot.send_message(
                            sender_id, f'Введите название группы, а со следующей строки разделяя переносом строки номера\n\n(Пример:\nГруппа 1\n79999999999\n):')

                        ed.give_item_data(DB_NAME, sender_id,
                                        'cash', 'groups:create')

                        bot.register_next_step_handler(msg, process.panel1_users)
                    elif group_action == 'delete':
                        mailings_groups = '\n\n'.join([line.split('(')[0] for line in ed.get_item_data(
                            DB_NAME, 'system', 'mailings_groups').split('\n')])
                        
                        msg = bot.send_message(
                            sender_id, f'Введите название группы для удаления (Пример: \nГруппа 1\n). Ваши группы: \n{mailings_groups}')

                        ed.give_item_data(DB_NAME, sender_id,
                                        'cash', 'groups:delete')

                        bot.register_next_step_handler(msg, process.panel1_users)
                    elif group_action == 'send':
                        
                        mailings_groups = '\n\n'.join([line.split('(')[0] for line in ed.get_item_data(
                            DB_NAME, 'system', 'mailings_groups').split('\n')])
                        
                        
                        msg = bot.send_message(
                            sender_id, f'Введите название группы для отправки\nДоступные группы:\n\n{mailings_groups}')

                        ed.give_item_data(DB_NAME, sender_id,
                                        'cash', 'groups:send')

                        bot.register_next_step_handler(msg, process.panel1_users)
                    elif group_action == 'info':
                        mailings_groups = '\n\n'.join([line.split('(')[0] for line in ed.get_item_data(
                            DB_NAME, 'system', 'mailings_groups').split('\n')])
                        
                        
                        msg = bot.send_message(
                            sender_id, f'Введите название группы для получения информации\nДоступные группы:\n\n{mailings_groups}')

                        ed.give_item_data(DB_NAME, sender_id,
                                        'cash', 'groups:info')

                        bot.register_next_step_handler(msg, process.panel1_users)

                if len(call.data.split(':')) == 2: # Выбор типа рассылки
                    mailing_type = call.data.split(':')[1]

                    if mailing_type == 'numbers':
                        msg = bot.send_message(
                            sender_id, f'Введите номера для рассылки разделяя переносом строки\n\n(Пример:\n79999999999\n79999999999\n):')
                        bot.register_next_step_handler(msg, process.panel1_users)
                    elif mailing_type == 'cities':
                        msg = bot.send_message(
                            sender_id, f'Введите города для рассылки разделяя переносом строки (Пример: Москва):')
                        bot.register_next_step_handler(msg, process.panel1_users)
                    elif mailing_type == 'groups':
                        keyboard = types.InlineKeyboardMarkup(row_width=1)
                        button1 = types.InlineKeyboardButton(
                            text="⚒️ Создать группу", callback_data=f'panel1:groups:create')
                        button2 = types.InlineKeyboardButton(
                            text="🗑️ Удалить группу", callback_data=f'panel1:groups:delete')
                        button3 = types.InlineKeyboardButton(
                            text="📄 Информация группы", callback_data=f'panel1:groups:info')
                        button4 = types.InlineKeyboardButton(
                            text="📨 Создать рассылку", callback_data=f'panel1:groups:send')
                        keyboard.add(button1, button2, button3, button4)
                        bot.send_message(sender_id, f'Выберите действие с группами:',
                                        reply_markup=keyboard)
                    elif mailing_type == '1c':
                        msg = bot.send_message(
                            sender_id, f'Введите по какому столбцу идет рассылка и необходимые значения разделяя все переносом строки.\nОтсутствие данных можно отметить как <_>\nЛюбое значение, кроме его отстутствия, можно отметить как <any>\n\n(Пример: \nДолг / оплата прошла:\nДолг\n<_>\n):')
                        bot.register_next_step_handler(msg, process.panel1_users)

                elif len(call.data.split(':')) == 1: # Меню рассылки

                    keyboard = types.InlineKeyboardMarkup(row_width=1)
                    button1 = types.InlineKeyboardButton(
                        text="🔢 Номера и ID", callback_data=f'panel1:numbers')
                    button2 = types.InlineKeyboardButton(
                        text="🏢 Города", callback_data=f'panel1:cities')
                    button3 = types.InlineKeyboardButton(
                        text="📂 Группы", callback_data=f'panel1:groups')
                    button4 = types.InlineKeyboardButton(
                        text="💼 Интеграция с 1C", callback_data=f'panel1:1c')
                    keyboard.add(button1, button2, button3, button4)

                    bot.send_message(sender_id, f'Выберите тип рассылки:',
                                    reply_markup=keyboard)
            if call.data.split(':')[0] == 'panel13':
                sender_id = call.from_user.id
                if len(call.data.split(':')) == 3:
                    user_id = call.data.split(':')[1]
                    role = call.data.split(':')[2]

                    ed.give_item_data(DB_NAME, user_id, 'role', role)
                    bot.send_message(
                        sender_id, f'Роль {role} установлена для пользователя {user_id}!')
                elif len(call.data.split(':')) == 1:
                    msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                    bot.register_next_step_handler(msg, process.panel13_id)
            if call.data.split(':')[0] == 'panel2':
                sender_id = call.from_user.id
                msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                bot.register_next_step_handler(msg, process.panel2_id)
            if call.data.split(':')[0] == 'panel4':
                sender_id = call.from_user.id
                msg = bot.send_message(
                    sender_id, f'Введите ID или текст сообщения:')

                bot.register_next_step_handler(msg, process.panel4_id)
            if call.data.split(':')[0] == 'panel5':
                sender_id = call.from_user.id
                msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                bot.register_next_step_handler(msg, process.panel5_id)
            if call.data.split(':')[0] == 'panel9':
                sender_id = call.from_user.id
                msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                bot.register_next_step_handler(msg, process.panel9_id)
            if call.data.split(':')[0] == 'panel16':
                sender_id = call.from_user.id
                if len(call.data.split(':')) == 3:
                    user_id = call.data.split(':')[1]
                    ban = call.data.split(':')[2]

                    ed.give_item_data(DB_NAME, user_id, 'ban', ban)
                    bot.send_message(
                        sender_id, f'Уровень блока {ban} установлен для пользователя {user_id}!')
                elif len(call.data.split(':')) == 1:
                    msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                    bot.register_next_step_handler(msg, process.panel16_id)
            if call.data.split(':')[0] == 'panel14':
                sender_id = call.from_user.id
                ed.give_item_data(DB_NAME, 'system', 'bot', '1')
                hype = Hyperion()
                bot.send_message(sender_id, '🟢 Бот снова работает!')
            if call.data.split(':')[0] == 'panel15':
                sender_id = call.from_user.id
                ed.give_item_data(DB_NAME, 'system', 'bot', '0')
                bot.send_message(sender_id, '🔴 Бот на технической паузе!')
            if call.data.split(':')[0] == 'panel8':
                sender_id = call.from_user.id
                messengers_counter = {}
                for user_id in ed.ids(DB_NAME):
                    user_id_messenger = ed.get_item_data(DB_NAME, user_id, 'from')
                    if user_id_messenger:
                        if messengers_counter.get(user_id_messenger) is not None:
                            messengers_counter[user_id_messenger] += 1
                        else:
                            messengers_counter[user_id_messenger] = 1
                    
                most_popular_messenger = ''
                for messenger in list(messengers_counter.keys())[:3]:
                    percent = (messengers_counter[messenger] / sum(messengers_counter.values())) * 100
                    filled = '█' * int(percent / 10)
                    empty = '░' * (10 - len(filled))
                    info =  f"{filled}{empty} {percent:.1f}%"
                    most_popular_messenger  += f'{messenger}: {info}\n  '
                
                cities_counter = {}
                for user_id in ed.ids(DB_NAME):
                    user_id_city = ed.get_item_data(DB_NAME, user_id, 'city')
                    if user_id_city:
                        if cities_counter.get(user_id_city) is not None:
                            cities_counter[user_id_city] += 1
                        else:
                            cities_counter[user_id_city] = 1
                            
                most_popular_city = ''
                for city in sorted(list(cities_counter.keys()), key=lambda x: cities_counter[x], reverse=True)[:5]:
                    percent = (cities_counter[city] / sum(cities_counter.values())) * 100
                    filled = '█' * int(percent / 10)
                    empty = '░' * (10 - len(filled))
                    info =  f"{filled}{empty} {percent:.1f}%"
                    most_popular_city += f'{city}: {info}\n'   
                
                operator_calls = []
                for id in ed.ids(DB_NAME):
                    author_id = ed.get_item_data(DB_NAME, id, 'author')
                    if author_id:
                        operator_calls.append(author_id)
                operator_calls = set(operator_calls)
                        
                ai_works = []
                for id in ed.ids(DB_NAME):
                    id_name = ed.get_item_data(DB_NAME, id, 'name')
                    if id_name != '' and id not in operator_calls:
                        ai_works.append(id)
                ai_works = set(ai_works)
                print('\n'.join(ai_works))
                        
                users_count = len([id for id in ed.ids(DB_NAME) if ed.get_item_data(DB_NAME, id, 'name')])
                
                messages_count = len(ed.ids(CHATS))
                
                average_time_generation = ed.average_item_data('ai', 'need_time')
                        
                searches = {}
                visual_search_types = {'rss': 'RELP', 'tse': 'TSE', 'rss_cache': 'RELP_cache', 'gh': 'GH', 'XGB+GH': 'GH', 'rss8': 'RELP', 'rss3': 'RELP'}
                for id in ed.ids('ai'):
                    id_search_type = ed.get_item_data('ai', id, 'search_type')
                    id_search_type = id_search_type if not visual_search_types.get(id_search_type) else visual_search_types.get(id_search_type)
                    if id_search_type:
                        if searches.get(id_search_type) is not None:
                            searches[id_search_type] += 1
                        else:
                            searches[id_search_type] = 1
                
                searches['FF_4.0'] = len(ed.ids('ai')) - sum(list(searches.values()))
                
                most_popular_search_type = ''        
                for search_type in list(searches.keys()):
                    percent = (searches[search_type] / sum(searches.values())) * 100
                    filled = '█' * int(percent / 10)
                    empty = '░' * (10 - len(filled))
                    info =  f"{filled}{empty} {percent:.1f}%"
                    most_popular_search_type += f'{search_type}: {info}\n   '
                
                
                chat_lenght_counter = {}
                for msg_id in ed.ids(CHATS):
                    msg_id_sender = ed.get_item_data(CHATS, msg_id, 'user_id')
                    if msg_id_sender:
                        if chat_lenght_counter.get(msg_id_sender) is not None:
                            chat_lenght_counter[msg_id_sender] += 1
                        else:
                            chat_lenght_counter[msg_id_sender] = 1
                            
                average_chat_length = sum(list(chat_lenght_counter.values())) / len(list(chat_lenght_counter.values()))
                
                
                
                stat_message = f"""
    📊 СТАТИСТИКА БОТА


    👥 Общее количество пользователей: {users_count}
    ✉️ Всего сообщений: {messages_count}
    📞 Уникальных сессий: {len(operator_calls)}
    
    🛡️ Процент отбития: {(1 - (len(operator_calls) / users_count)) * 100}%
    
    ⏱ Среднее время ответа ИИ: {average_time_generation:.1f} сек
    💬 Средняя длина диалога: {average_chat_length:.1f} сообщ.

    📍 ТОП ГОРОДОВ:
    {most_popular_city}

    📱 ТОП МЕССЕНДЖЕРОВ:
    {most_popular_messenger}

    🔍 СТАТИСТИКА ПОИСКА:
    {most_popular_search_type}

    🔄 Данные обновлены: {datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime('%d.%m.%Y %H:%M')}
    """
                bot.send_message(sender_id, stat_message)
    
                # bot.send_message(sender_id, f'Примеры работы ИИ:\n {'\n'.join(ai_works)}')
    
            if call.data.split(':')[0] == 'panel10':    
                sender_id = call.from_user.id
                if len(call.data.split(':')) == 1:
                    keyboard = types.InlineKeyboardMarkup(row_width=1)
                    button1 = types.InlineKeyboardButton(
                        text="⏳ Закрыть старые сессии", callback_data=f'panel10:close')
                    button2 = types.InlineKeyboardButton(
                        text="✒️ Смета открытых сессий", callback_data=f'panel10:sessions')
                    button3 = types.InlineKeyboardButton(
                        text="👑 Топ операторов ✖️", callback_data=f'panel10:ops_top')
                    button4 = types.InlineKeyboardButton(
                        text="☎️ Создать сессию", callback_data=f'panel3')
                    keyboard.add(button1, button2, button3, button4)

                    bot.send_message(sender_id, f'Выберите тип действия:',
                                    reply_markup=keyboard)
                if len(call.data.split(':')) == 2:
                    action_type = call.data.split(":")[1]
                    
                    if action_type == 'close':
                        
                        close_counter = 0
                        
                        user_ids = ed.ids(DB_NAME)
                        for id in user_ids:
                            id_data = ed.get_id_data(DB_NAME, id)
                            if 'date' not in id_data.keys(): continue
                            if str(id_data["date"]) == '0': continue
                            if int(id_data["date"].split('.')[1]) < int(datetime.date.today().month):
                                country = id_data["country"]
                                main_chat = main_chat_rus if country == 'Россия' else main_chat_kz
                                
                                try:
                                    bot.delete_forum_topic(main_chat, int(id_data['chat_id']))
                                    print(f'Успешно удален чат {id}')
                                except: pass
                                
                                id_data["date"] = 0
                                id_data['status'] = 'stable'
                                id_data['chat_id'] = 0
                                
                                ed.give_id_data(DB_NAME, id, id_data)
                                
                                print(f'Данные пользователя {id} обновлены')
                                
                                try:
                                    bot.send_message(id, 'Время сессии истекло. Если ваша проблема все еще актуальна - позовите оператора снова!')
                                except: pass
                                
                                close_counter += 1
                        bot.send_message(sender_id, f'Кол-во закрытых сессий: {close_counter}')
                        
                        
                    elif action_type == 'sessions':
                        
                        active_session_counter = {}
                        waiting_session_counter = {}
                        for id in ed.ids(DB_NAME):
                            id_data = ed.get_id_data(DB_NAME, id)
                            
                            if 'status' not in id_data.keys(): continue
                            
                            status = id_data['status']
                            chat_id = id_data["chat_id"]
                            date = id_data["date"]        
                            try: country = id_data["country"]
                            except: country = 'Россия'                     
                            
                            main_chat = main_chat_rus if country == 'Россия' else main_chat_kz
                            main_chat = str(main_chat)[4:]
                            
                            if status == 'session': active_session_counter[chat_id] = (id, date, main_chat)
                            elif status == "waiting": waiting_session_counter[chat_id] = (id, date, main_chat)
                        
                        active_session_texts, waiting_session_texts = [], []
                        
                        file_text = '📞 Активные сессии:\n\n' 
                        for session_id, data in active_session_counter.items():
                            active_session_texts.append(f'U: {data[0]}; S: {session_id}; D: {data[1]} - https://t.me/c/{data[2]}/{session_id}\n')
                            
                        active_session_texts.sort(key=lambda x: int(x.split()[6].split('.')[1]))
                        file_text += '\n'.join(active_session_texts)
                        
                        file_text += '\n\n⌚ Ожидающие сессии:\n\n'
                        for session_id, data in waiting_session_counter.items():
                            waiting_session_texts.append(f'U: {data[0]}; S: {session_id}; D: {data[1]} - https://t.me/c/{data[2]}/{session_id}\n')
                            
                        waiting_session_texts.sort(key=lambda x: int(x.split()[6].split('.')[1]))
                        file_text += '\n'.join(waiting_session_texts)
                        
                        
                            
                        text = '📊 Статистика сессий'
                        text += f"\n\nВсего открытых сессий: {len(active_session_counter.keys()) + len(waiting_session_counter.keys())}"
                        text += f"\n\nАктивных сессий: {len(active_session_counter.keys())}"
                        text += f"\n\nОжидающх сессий: {len(waiting_session_counter.keys())}"
                        text += '\n\n* Старые сессии могут не работать из-за несовместимости данных!'
                        
                        with open('session_info.txt', 'w', encoding='utf8') as f:
                            f.write(file_text)

                        bot.send_document(sender_id, document=open(
                            'session_info.txt', 'rb'), caption=text)

                        session.safe_remove('session_info.txt')
                        
                                
                    elif action_type == 'ops_top':
                        ...
            if call.data.split(':')[0] == 'panel3':
                sender_id = call.from_user.id
                msg = bot.send_message(sender_id, f'Введите ID пользователя:')

                bot.register_next_step_handler(msg, process.panel3_id)
            if call.data.split(':')[0] == 'panel18':
                sender_id = call.from_user.id
                if len(call.data.split(':')) == 1:
                    keyboard = types.InlineKeyboardMarkup(row_width=1)
                    button1 = types.InlineKeyboardButton(
                        text="🔎 Запросить чат", callback_data=f'panel2')
                    button2 = types.InlineKeyboardButton(
                        text="🔎 Запросить данные сообщения", callback_data=f'panel4')
                    button3 = types.InlineKeyboardButton(
                        text="🔎 Запросить данные пользователя", callback_data=f'panel5')
                    keyboard.add(button1, button2, button3)

                    bot.send_message(sender_id, f'Выберите тип действия:',
                                    reply_markup=keyboard)
                


    def consultation(self, message):
        sender_id = int(message.from_user.id)
        message_text = str(message.text or '')
        query = ed.get_item_data(DB_NAME, sender_id, "cash")
        ed.give_item_data(DB_NAME, sender_id, 'cash', '')
        last_id = int(ed.get_item_data('faq', 'system', 'last_id'))
        qa = {'question': query, 'answer': message_text}
        ed.give_id_data('faq', last_id+1, qa)
        ed.give_item_data('faq', 'system', 'last_id', last_id+1)
        bot.send_message(sender_id, 'Ответ на вопрос сохранен! Спасибо за помощь, буду знать :)')
                
    def panel1_users(self, message):
        sender_id = int(message.from_user.id)
        message_text = str(message.text or '')
        message_data = str(message.text or '').split('\n')

        cash = ed.get_item_data(DB_NAME, sender_id, 'cash')

        if cash == 'groups:create':
            group_name = message_data[0]
            group_numbers = message_data[1:]
            
            mailings_groups = ed.get_item_data(
                DB_NAME, 'system', 'mailings_groups')
            
            mailings_groups_names = [line.split('(')[0] for line in ed.get_item_data(
                        DB_NAME, 'system', 'mailings_groups').split('\n')]
            
            if group_name in mailings_groups_names:
                bot.send_message(sender_id, f'Группа {group_name} уже существует!')
                return
            
            new_data = f'{mailings_groups}{group_name}({'; '.join(group_numbers)})\n'
            
            ed.give_item_data(DB_NAME, 'system', 'mailings_groups', new_data)
            
            bot.send_message(sender_id, f'Группа {group_name} добавлена!')
            return
        elif cash == 'groups:delete':
            mailings_groups = ed.get_item_data(
                DB_NAME, 'system', 'mailings_groups').split('\n')
            
            mailings_groups_names = [line.split('(')[0] for line in ed.get_item_data(
                        DB_NAME, 'system', 'mailings_groups').split('\n')]
            
            if message_text not in mailings_groups_names:
                bot.send_message(sender_id, 'Группа не найдена!')
                return

            for group in mailings_groups:
                if group.startswith(message_text):
                    mailings_groups.remove(group)

            new_data = '\n'.join(mailings_groups)

            ed.give_item_data(DB_NAME, 'system',
                            'mailings_groups', new_data)
            
            bot.send_message(sender_id, f'Группа {message_text} удалена!')
            
            return
        elif cash == 'groups:send':
            mailings_groups = ed.get_item_data(
                DB_NAME, 'system', 'mailings_groups').split('\n')
            
            mailings_groups_names = [line.split('(')[0] for line in ed.get_item_data(
                        DB_NAME, 'system', 'mailings_groups').split('\n')]
            
            if message_text not in mailings_groups_names:
                bot.send_message(sender_id, 'Группа не найдена!')
                return

            for group in mailings_groups:
                if group.startswith(message_text):
                    numbers = re.search(r'\(([^)]*)\)', group).group(1).split('; ')
                    message_text = '\n'.join(numbers)                
        elif cash == 'groups:info':
            mailings_groups = ed.get_item_data(
                DB_NAME, 'system', 'mailings_groups').split('\n')
            
            mailings_groups_names = [line.split('(')[0] for line in ed.get_item_data(
                        DB_NAME, 'system', 'mailings_groups').split('\n')]
            
            if message_text not in mailings_groups_names:
                bot.send_message(sender_id, 'Группа не найдена!')
                return

            for group in mailings_groups:
                if group.startswith(message_text):
                    numbers = re.search(r'\(([^)]*)\)', group).group(1).split('; ')
                    group_ids = '\n'.join(numbers) 
                    
                    bot.send_message(sender_id, f'Вот список ID группы {message_text}:\n{group_ids}')      
                    
            return   

        ed.give_item_data(DB_NAME, sender_id, 'cash', message_text)

        msg = bot.send_message(sender_id, f'Введите текст рассылки:')

        bot.register_next_step_handler(msg, self.panel1_text)


    def panel1_text(self, message):
        sender_id = int(message.from_user.id)
        data = [el.strip() for el in str(ed.get_item_data(DB_NAME, sender_id, 'cash')).replace('\n\n', '\n').split('\n')]
        ed.give_item_data(DB_NAME, sender_id, 'cash', '')
        
        text, file_text = self.mailings_agent.send(sender_id, data, message)
        
        print('Подтверждаю переход в Панель')

        with open('mailings.txt', 'w', encoding='utf8') as f:
            f.write(file_text)
            
        print(text)

        bot.send_document(sender_id, document=open(
            'mailings.txt', 'rb'), caption=text)

        self.session_agent.safe_remove('mailings.txt')


    def panel13_id(self, message):
        sender_id = int(message.from_user.id)
        message_id = message.text

        if message_id not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        button1 = types.InlineKeyboardButton(
            text="👑 Админ", callback_data=f'panel13:{message_id}:admin')
        button2 = types.InlineKeyboardButton(
            text="🧢 Оператор", callback_data=f'panel13:{message_id}:operator')
        keyboard.add(button1, button2)

        bot.send_message(sender_id, f'Выберите роль пользователю:',
                        reply_markup=keyboard)


    def panel2_id(self, message):
        sender_id = int(message.from_user.id)
        message_id = int(message.text)

        if str(message_id) not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        self.session_agent.send_chat_history(message_id, sender_id)


    def panel4_id(self, message, message_id=None):
        # sourcery skip: default-get, remove-dict-keys
        sender_id = int(message.from_user.id)
        message_id = message_id if message_id else message.text

        if message_id not in ed.ids(CHATS):
            for msg in ed.ids(CHATS):
                if message_id == ed.get_item_data(CHATS, msg, 'message'):
                    self.panel4_id(message, msg)
            return

        user_id = ed.get_item_data(CHATS, message_id, 'user_id')
        chat_id = ed.get_item_data(CHATS, message_id, 'chat_id')
        time = ed.get_item_data(CHATS, message_id, 'time')
        text = ed.get_item_data(CHATS, message_id, 'message')
        type = ed.get_item_data(CHATS, message_id, 'message_type')
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        button1 = types.InlineKeyboardButton(
            text="🔎 Получить чат", callback_data=f'panel2')
        keyboard.add(button1)

        text = f'''Данные по #{message_id}:

        ✔ Пользователь: {user_id}
        ✔ Чат: {chat_id}
        ✔ Время: {time}
        ✔ Текст: {text}
        ✔ Тип: {type}
        '''
        
        visual = {'keywords': 'Ключевые слова',
            'context': 'Ситуация',
            'need_time': 'Затрачено времени (в сек.)',
            'faq': 'Поиск',
            'autolearning': 'Автообучение',
            'answer': 'Ответ',
            'contain': 'Запрос',
            'search_type': 'Сценарий поиска',
            'repeat_test': 'Отсутствие повтора',
            'question_test': 'Наличие вопроса',
            'response': 'Ответ'}
        
        if message_id in ed.ids('ai'):
            message_data = ed.get_id_data('ai', message_id)
        
            text += f'\n\nДанные ИИ генерации:\n'

            for key in message_data:
                
                if key == 'faq': continue
                
                visual_key = visual[key] if key in visual.keys() else key
                text += f"\n\n✔ {visual_key}: {message_data[key]}"
            
            try:
                with open('search_response.txt', 'w', encoding='utf8') as f:
                    f.write(message_data['faq'])
                bot.send_document(sender_id, document=open(
                    'search_response.txt', 'rb'), caption=text)
            except:
                bot.send_message(sender_id, text)
                
            
            self.session_agent.safe_remove('search_response.txt')
            
            
    def panel5_id(self, message, message_id=None):
        sender_id = int(message.from_user.id)
        message_id = message_id if message_id else message.text

        if message_id not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        user_data = ed.get_id_data(DB_NAME, message_id)

        visual = {'ban': 'Уровень блокировки',
                'from': 'Мессенджер',
                'role': 'Роль',
                'city': 'Город',
                'name': 'Имя',
                'phone_number': 'Номер телефона',
                'country': 'Страна',
                'verify': 'Уровень верификации',
                'date': 'Дата сессии',
                'status': 'Статус',
                'chat_id': 'ID чата',
                'cash': 'Сохренный кэш'}

        text = f'Данные по {message_id}:\n'

        for key in user_data:
            visual_key = visual[key] if key in visual.keys() else key
            text += f"\n✔ {visual_key}: {user_data[key]}"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        button1 = types.InlineKeyboardButton(
            text="🔎 Получить чат", callback_data=f'panel2')
        keyboard.add(button1)

        bot.send_message(sender_id, text, reply_markup=keyboard)


    def panel9_id(self, message):
        sender_id = int(message.from_user.id)
        message_id = message.text

        if message_id not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        ed.give_item_data(DB_NAME, message_id, 'status', 'stable')
        ed.give_item_data(DB_NAME, message_id, 'chat_id', 0)
        ed.give_item_data(DB_NAME, message_id, 'verify', 0)

        bot.send_message(
            sender_id, f'Данные пользователя {message_id} успешно сброшены!')


    def panel16_id(self, message):
        sender_id = int(message.from_user.id)
        message_id = message.text

        if message_id not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        button1 = types.InlineKeyboardButton(
            text="💢 Запрет вызова", callback_data=f'panel16:{message_id}:1')
        button2 = types.InlineKeyboardButton(
            text="🛑 Полная блокировка", callback_data=f'panel16:{message_id}:2')
        button3 = types.InlineKeyboardButton(
            text="❎ Разблокировка", callback_data=f'panel16:{message_id}:0')
        keyboard.add(button1, button2, button3)

        bot.send_message(sender_id, f'Выберите уровень блокировки',
                        reply_markup=keyboard)

    def panel3_id(self, message):
        sender_id = int(message.from_user.id)
        message_id = message.text

        if message_id not in ed.ids(DB_NAME):
            bot.send_message(
                sender_id, f'⚠️ Ошибка! Данный пользователь не найден!')
            return

        self.session_agent.create_session(message_id)

        bot.send_message(
            sender_id, f'Для пользователя {message_id} успешно создана сессия!')

class SessionAgent:

    def create_session(self, sender_id):
        print('Зафиксирован вызов оператора')
        user_id = sender_id
        user_data = ed.get_id_data(DB_NAME, user_id)
        
        main_chat = main_chat_rus if user_data['country'] == 'Россия' else main_chat_kz

        name = user_data['name']
        city = user_data['city']
        phone_number = user_data['phone_number']
        
        
        result = bot.create_forum_topic(
            main_chat,
            f'Nobody`s chat {user_id}'
        )

        user_chat_id = int(result.message_thread_id)
        bb.add(f'create_session:{user_id}', f'{user_chat_id}')
        
        user_data['status'] = 'waiting'
        user_data['chat_id'] = user_chat_id
        user_data['date'] = datetime.datetime.now(pytz.timezone("Europe/Moscow")).strftime('%H:%M %d.%m')
        ed.give_id_data(DB_NAME, user_id, user_data)

        history = chat_history(sender_id)

        self.send_chat_history(sender_id)
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        button1 = types.InlineKeyboardButton(
                    text="Закрыть сессию", callback_data=f'end_session:{sender_id}')

        keyboard.add(button1)
        
        bot.send_message(
            main_chat, 
            f'Данные пользователя:\nФИО: {name}\nГород: {city}\nНомер телефона: {phone_number}\nЧат: {user_id}\nID сессии: {user_chat_id}\nМессенджер: Telegram', 
            message_thread_id=user_chat_id,
            reply_markup=keyboard)

        qa = hype.analize(history)

        keyboard = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(
            text="Поднять чат", callback_data=f'accept:{user_chat_id}')
        keyboard.add(button1)

        text = f'Поступил вызов от {sender_id}\nДля принятия, напишите в соответствующий чат. Нажатие на кнопку опционально\n\nТематика вызова: {qa[0]}'

        message = bot.send_message(main_chat, text, reply_markup=keyboard)
        message_id = message.message_id
        
        user_chat_data = {
            'author': user_id,
            'question': '',
            'answer': '',
            'notification': message_id,
            'operator': 0
                        }

        ed.give_id_data(DB_NAME, user_chat_id, user_chat_data)

        return user_chat_id

    def close_session(self, user_id):
        messanger = ed.get_item_data(DB_NAME, user_id, 'from')
        main_chat = main_chat_rus if ed.get_item_data(
            DB_NAME, user_id, 'country') == 'Россия' else main_chat_kz

        user_chat_id = int(ed.get_item_data(DB_NAME, user_id, 'chat_id'))
        
        bot.send_message(main_chat, 'Вы закончили сессию!',
                        message_thread_id=user_chat_id)

        ed.give_item_data(DB_NAME, user_id, 'status', 'stable')
        ed.give_item_data(DB_NAME, user_id, 'chat_id', 0)

        try:
            if messanger == 'whatsapp':
                greenAPI.sending.sendMessage(
                    f"{user_id}@c.us", 'Оператор вышел из чата. Надеемся, мы смогли решить твою проблему!')
            elif messanger == 'telegram':
                bot.send_message(
                    user_id, 'Оператор вышел из чата. Надеемся, мы смогли решить твою проблему!')
        except:
            pass
            
        if ed.get_item_data(DB_NAME, 'system', 'analize') == 0:
            
            keyboard = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(
                text="Подтвердить", callback_data=f'cancel:{user_chat_id}')
            keyboard.add(button1)

            text = 'Пожалуйста, подвердите закрытие сессии'

            bot.send_message(main_chat, text, reply_markup=keyboard,
                            message_thread_id=user_chat_id)
            
            return
            
        history = chat_history(user_chat_id)

        qa = hype.analize(history)

        ed.give_item_data(DB_NAME, user_chat_id, 'question', qa[0])
        ed.give_item_data(DB_NAME, user_chat_id, 'answer', qa[1])

        keyboard = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(
            text="Подтвердить", callback_data=f'confirm:{user_chat_id}')
        button2 = types.InlineKeyboardButton(
            text="Повторный анализ", callback_data=f'again:{user_chat_id}')
        button3 = types.InlineKeyboardButton(
            text="Пропустить", callback_data=f'cancel:{user_chat_id}')
        keyboard.add(button1)
        keyboard.add(button2)
        keyboard.add(button3)

        text = f'''
        Пожалуйста, проверьте анализ чата!

        Вопрос:
        {qa[0]}

        Ответ:
        {qa[1]}
        '''

        bot.send_message(main_chat, text, reply_markup=keyboard,
                        message_thread_id=user_chat_id)
        
    def to_session_send(self, sender_id, message):  # от клиента к оператору
        message_type = message.content_type
        message_text = message.text or message.caption or ''
        entities = message.entities or message.caption_entities
        
        sender_data = ed.get_id_data(DB_NAME, sender_id)

        main_chat = main_chat_rus if sender_data['country'] == 'Россия' else main_chat_kz

        user_chat_id = int(sender_data['chat_id'])

        bb.add(f'to_session_send:{sender_id}', f'{message_text} | {message_type}')

        # chat_history(sender_id, sender_id, message_text, message_type)
        chat_history(user_chat_id, sender_id, message_text, message_type)

        bot.copy_message(main_chat, sender_id, message.message_id,
                        message_thread_id=user_chat_id)
        
        # if session_ia.predict(message_text) == 'end_session':
        #     keyboard = types.InlineKeyboardMarkup(row_width=1)
        #     button1 = types.InlineKeyboardButton(
        #         text="✅ Согласен", callback_data=f'end_session:{sender_id}')

        #     keyboard.add(button1)
        #     bot.send_message(main_chat, 'Предлагаю закрыть сессию 😇', reply_markup=keyboard, message_thread_id=user_chat_id)

    def to_client_send(self, sender_id, user_id, message):  # от оператора из телеграма к клиенту
        message_type = message.content_type
        message_text = message.text or message.caption or ''
        entities = message.entities or message.caption_entities
        
        user_data = ed.get_id_data(DB_NAME, user_id)

        messanger = user_data['from']

        main_chat = main_chat_rus if user_data['country'] == 'Россия' else main_chat_kz

        user_chat_id = int(user_data['chat_id'])
        
        try:
            if messanger == 'whatsapp':
                self.whatsapp_send_message(user_id, message)
            elif messanger == 'telegram':
                self.telegram_send_message(user_id, message)
        except:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button1 = types.InlineKeyboardButton(
                text="Закрыть сессию", callback_data=f'end_session:{user_id}')
            keyboard.add(button1)
            bot.send_message(main_chat, 'Сообщение не было доставлено :(', message_thread_id=user_chat_id, reply_markup=keyboard)

        bb.add(f'to_client_send:{user_id}', f'{message_text} | {message_type}')

        chat_history(user_id, sender_id, message_text, message_type)
        chat_history(user_chat_id, sender_id, message_text, message_type)

        if ed.get_item_data(DB_NAME, user_chat_id, 'operator') != int(sender_id):
            operator = bot.get_chat(sender_id).first_name
            emoji_id = int(str(sender_id)[0])*10 + int(str(sender_id)[-1])
            bot.edit_forum_topic(
                chat_id=main_chat,
                message_thread_id=user_chat_id,
                name=f'{operator}`s chat {user_id}',
                icon_custom_emoji_id=bot.get_forum_topic_icon_stickers()[emoji_id]['custom_emoji_id'])
            ed.give_item_data(DB_NAME, user_chat_id, 'operator', sender_id)

        if message_text.endswith('С уважением,\nStaffsharing.'):
            self.close_session(user_id)


        # if session_ia.predict(message_text) == 'end_session':
        #     keyboard = types.InlineKeyboardMarkup(row_width=1)
        #     button1 = types.InlineKeyboardButton(
        #         text="✅ Согласен", callback_data=f'end_session:{user_id}')

        #     keyboard.add(button1)
        #     bot.send_message(main_chat, 'Предлагаю закрыть сессию 😇', reply_markup=keyboard, message_thread_id=user_chat_id)
            
    def accept_session(self, sender_id, session_id):

        client_id = ed.get_item_data(DB_NAME, session_id, 'author')
        messenger = ed.get_item_data(DB_NAME, client_id, 'from')

        if ed.get_item_data(DB_NAME, client_id, 'status') == 'waiting':
            ed.give_item_data(DB_NAME, client_id, 'status', 'session')
            ed.give_item_data(DB_NAME, client_id, 'date', datetime.datetime.now(
                pytz.timezone("Europe/Moscow")).strftime('%H:%M %d.%m'))

            if messenger == 'whatsapp':
                response = greenAPI.sending.sendMessage(
                    f"{client_id}@c.us", 'Оператор присоединился к чату!')
            elif messenger == 'telegram':
                bot.send_message(client_id, 'Оператор присоединился к чату!')

        bb.add(f'accept_session', f'{session_id}')
        return client_id

    def telegram_send_message(self, chat_id, message: telebot.types.Message):
        message_type = message.content_type
        message_text = message.text or message.caption or ''
        entities = message.entities or message.caption_entities

        if message_type == "text":
            bot.send_message(
                chat_id=chat_id,
                text=message_text,
                entities=entities
            )
        elif message_type == "photo":
            bot.send_photo(
                chat_id=chat_id,
                # Берем самое высокое разрешение # type: ignore
                photo=message.photo[-1].file_id,
                caption=message_text,
                caption_entities=entities
            )
        elif message_type == "video":
            bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,  # type: ignore
                caption=message_text,
                caption_entities=entities
            )
        elif message_type == "document":
            bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,  # type: ignore
                caption=message_text,
                caption_entities=entities
            )
        else:
            bot.send_message(chat_id, 'Неподдерживаемый формат файла')
            
    def download_file(self, message: telebot.types.Message):
        message_type = message.content_type

        if message_type == 'photo':
            file_info = message.photo[-1]  # type: ignore
        elif message_type == 'video':
            file_info = message.video
        elif message_type == 'document':
            file_info = message.document
        else:
            bot.send_message(message.chat.id, 'Не поддерживаемый формат файла')
            return

        # Получаем файл
        file = bot.get_file(file_info.file_id)  # type: ignore
        downloaded_file = bot.download_file(file.file_path)  # type: ignore
        file_type = file.file_path.split('.')[-1]  # type: ignore

        # Сохраняем файл

        file_path = f"./{file_info.file_id}.{file_type}"  # type: ignore
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        file_name = Path(file_path).name

        return file_name

    def safe_remove(self, file_path, max_retries=5, delay=0.5):
        for _ in range(max_retries):
            try:
                os.remove(file_path)
                return True
            except PermissionError:
                time.sleep(delay)
        return False

    def whatsapp_send_message(self, chat_id, message: telebot.types.Message):
        message_type = message.content_type
        message_text = message.text or message.caption

        if message_type != 'text':
            file = self.download_file(message)

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

    def send_chat_history(self, sender_id, chat=None):
        if chat:
            main_chat = chat
            user_chat_id = 'General'
        else:
            main_chat = main_chat_rus if ed.get_item_data(
                DB_NAME, sender_id, 'country') == 'Россия' else main_chat_kz

            user_chat_id = ed.get_item_data(DB_NAME, sender_id, 'chat_id')

        history = chat_history(sender_id)

        max_history = int(ed.get_item_data(DB_NAME, 'system', 'max_history'))

        out_text = ''
        blocks = []
        authors = {}

        for msg_id in list(history.keys())[-1 * max_history:]:
            time = history[msg_id]['time']
            author_id = history[msg_id]['user_id']
            if author_id in authors.keys():
                author = authors[author_id]
            else:
                author = ed.get_item_data(DB_NAME, history[msg_id]['user_id'], 'name')
                authors[author_id] = author
            author = 'Hype BOT' if not author else author
            text = history[msg_id]['message']
            out_text += f'{author} {time}\n{text}\n\n'

        block_count = len(out_text) // 4000 + 1

        for n in range(block_count):
            block = out_text[n*4000:min((n+1)*4000, len(out_text))]
            blocks.append(block)

        for block in blocks:
            bot.send_message(main_chat, block,
                            message_thread_id=user_chat_id)  # type: ignore

class MailingsAgent(SessionAgent):
    def __init__(self):
        
        self.login = get_config().get('sms_login')
        self.password = get_config().get('sms_password')
        self.sms_url = 'https://api3.sms-agent.ru/v2.0/'
        super().__init__()
        
    def check_status(self, id):
        status_decoder = ['В очереди', 'Передано оператору связи', 'Доставлено', 'Не доставлено', 'Истек срок "жизни" сообщения', 'Недопустимое значение ID', 'ID не найдено']

        params_status = {
            'login': self.login,
            'pass': self.password,
            'act': 'status',
            'id': id
        }
        
        response_status = int(requests.get(self.sms_url, params=params_status).text)
        return status_decoder[response_status]
    
    def sms_send(self, numbers: list, text: str):
        print(f'Получены на вход: {numbers}')
        params = {
            'login': self.login,
            'pass': self.password,
            'act': 'send',
            'from': 'Sharing', # Нужно проверить на счет имен :(
            'to': ','.join(numbers),
            'text': text
        }
        response = requests.get(self.sms_url, params=params)
        if response.status_code != 200: raise Exception('Не удалось связаться с сервером!')
        sms_ids = response.text.split(',')
        print(f'ID сообщеий: {sms_ids}')
        
        try: map(int, sms_ids)
        except: raise Exception('Ошибка запроса на сервер!')

        if len(sms_ids) != len(numbers): 
            print(f'N: {len(numbers)}, I: {len(sms_ids)}')
            raise Exception('Кол-во статусов не совпадает с кол-вом номеров рассылки!')
        
        success = []
        unsuccess = []
        waiting = []
        error = []
        base = {}
        
        for i in range(len(sms_ids)): 
            base[numbers[i]] = sms_ids[i]
        
        for number, id in base.items():
            status = self.check_status(id)
            
            print(f'Номер: {number} - ID: {id} - Статус: {status}')
            
            if status == 'Доставлено': success.append(number)
            elif status == 'Не доставлено': unsuccess.append(number)
            elif status == 'В очереди' or status == 'Передано оператору связи': waiting.append(number)
            else: error.append(number)
        
        if len(waiting) != 0: 
            for number in waiting:
                status = self.check_status(base[number])
                
                if status == 'Доставлено': success.append(number)
                elif status == 'Не доставлено': unsuccess.append(number)
                else: error.append(number)
                
        print(f'Модуль СМС завершил работу! {success}, {unsuccess}, {error}')
        
        return success, unsuccess, error

    def send(self, sender_id: str, data: list, message: telebot.types.Message):


        successful = []
        found = []
        
        whatsapp_user = []
        telegram_user = []
        groups = []
        
        not_user = []
        not_found = []
        errors = []

        for i in range(len(data)):
            data.pop(i) if data[i] == '' else None

        for id in ed.ids(DB_NAME):
            id_number = str(ed.get_item_data(DB_NAME, id, 'phone_number'))
            id_city = str(ed.get_item_data(DB_NAME, id, 'city'))
            
            if not id_number or not id_city: continue # Если не пользователь - пропускаем (пока)

            for s in '+-()': # Исправляем ввод клиента
                id_number = id_number.replace(s, '')
            if id_number[0] == '8':
                id_number = '7' + id_number[1:]

            if str(id_number) in data: # Найдено совпадение по номеру телефона
                try:
                    if ed.get_item_data(DB_NAME, id, 'from') == 'telegram': # Для клиентов из Telegram
                        bot.copy_message(id, message.chat.id, message.id)
                        telegram_user.append(id)
                    elif ed.get_item_data(DB_NAME, id, 'from') == 'whatsapp': # Для клиентов из WhatsApp
                        self.whatsapp_send_message(id, message)
                        whatsapp_user.append(id)
                    found.append(id_number)
                except:
                    errors.append(id)
                    
            elif id_city in data: # Найдено совпадение по городу
                try:
                    if ed.get_item_data(DB_NAME, id, 'from') == 'whatsapp': # Для клиентов из WhatsApp
                        self.whatsapp_send_message(id, message)
                        whatsapp_user.append(id)
                    elif ed.get_item_data(DB_NAME, id, 'from') == 'telegram': # Для клиентов из Telegram
                        bot.copy_message(id, message.chat.id, message.id)
                        telegram_user.append(id)
                    found.append(id_city)
                except:
                    errors.append(id)

            elif str(id) in data: # Найдено совпадение по ID
                try:
                    if ed.get_item_data(DB_NAME, id, 'from') == 'whatsapp': # Для клиентов из WhatsApp
                        self.whatsapp_send_message(id, message)
                        whatsapp_user.append(id)
                    elif ed.get_item_data(DB_NAME, id, 'from') == 'telegram': # Для клиентов из Telegram
                        bot.copy_message(id, message.chat.id, message.id)
                        telegram_user.append(id)
                    found.append(id)
                except:
                    errors.append(id)

        not_found = [f for f in data if f not in found] # Все что в data но не в found - идет на 2-ой этап
        sms_mailing = []
        
        if data[0] in request_gh.get_list_of_items('1С:'): # Если 1-ый элемент рассылки является столбцом таблицы...
            item = data[0]
            values = data[1:]
            nums = request_gh.get_nums_by_item(item, values)
            ed.give_item_data(DB_NAME, sender_id, 'cash', '\n'.join(nums))
            self.panel1_text(message)
            return
        if data[0] in request_gh.get_list_of_items('Реестр Физ. лицо:'):
            item = data[0]
            values = data[1:]
            nums = request_gh.get_nums_by_item(item, values)
            ed.give_item_data(DB_NAME, sender_id, 'cash', '\n'.join(nums))
            self.panel1_text(message)
            return
        
        for id in not_found:
            for s in '+-()': # На всякий случай сразу нормализуем номер телефона
                id = id.replace(s, '')
            if id[0] == '8':
                id = '7' + id[1:]
            if len(id) >= 11 and str(id).isdigit(): # Определяем номер телефона
                
                sms_mailing.append(id)
                    
                # self.session_agent.whatsapp_send_message(id, message)
                # not_user.append(id)
                # found.append(id)
            
            elif str(id)[0] == '-': # Если попался номер группы
                try:
                    bot.copy_message(id, message.chat.id, message.id)
                    groups.append(id)
                    found.append(id)
                except:
                    bot.send_message(id, message.text)
            elif str(id).isdigit(): # На всякий случай пробиваем Telegram
                try:
                    bot.copy_message(id, message.chat.id, message.id)
                    not_user.append(id)
                    found.append(id)
                except: pass
        print(f'Запускаю СМС модуль по номерам: {sms_mailing}')
        sms_results = self.sms_send(sms_mailing, message.text)
        print('Подтверждаю окончание работы СМС модуля')
        not_user += sms_results[0]
        found += sms_results[0]
        not_found += sms_results[1]
        errors += sms_results[2]
                
                
        not_found = [f for f in data if f not in found]
        all_mails = str(len(whatsapp_user) + len(not_user) + len(telegram_user) + len(groups))
        
        warning_1 = '⚠️' if len(not_user) > 50 or len(not_user) > len(data) * 0.5 else ''
        warning_2 = '⚠️' if len(errors) != 0 else ''
        warning_3 = '⚠️' if len(found) / len(data) < 0.95 else ''

        text = f'''📃 Отчет об отправке:

        📤 Отправлено: {all_mails} сообщений
        
        ✅ Отработаны вводные данные: {len(found)}/{len(data)} {warning_3}
        
        ✔️ Отправлено в WhatsApp: {len(whatsapp_user)}
        ✔️ Отправлено в Telegram: {len(telegram_user)}
        
        🤝 Группы: {len(groups)}

        ❔ Не пользователи бота: {len(not_user)} {warning_1}

        ❓ Не найдено: {len(not_found)}
        ⛔️ Ошибки: {len(errors)} {warning_2}
        '''

        errors = '    \n'.join(errors)
        successful = '    \n'.join(successful)
        whatsapp = '    \n'.join(whatsapp_user)
        telegram = '    \n'.join(telegram_user)
        groups = "    \n".join(groups)
        not_user = "    \n".join(not_user)
        found = '    \n'.join(found)
        not_found = '    \n'.join(not_found)

        file_text = f'''Отчет об отправке:

        Всего отправлено: {all_mails} сообщений
            
        Отработаны вводные данные:
    {found}

        Пользователи бота из WhatsApp: 
    {whatsapp}
        Пользователи бота из Telegram: 
    {telegram}
        Группы:
    {groups}

        Не пользователи бота: 
    {not_user}

        Не найдено: 
    {not_found}
        Ошибки: 
    {errors}
            '''
        print('Возвращаю данные рассылки классу Панели')
        return text, file_text

def _add_to_chat_history(chat_id, thread_id, sender_id, message_text):
    if chat_id in [main_chat_rus, main_chat_kz]:
        history = chat_history(thread_id, sender_id, message_text)
    else:
        history = chat_history(chat_id, sender_id, message_text)
        
    return history

@bot.message_handler(content_types=telebot.util.content_type_media) #, chat_types=['private', 'supergroup']
def handler(message):
    run_async(async_handler(message))
    
async def async_handler(message):
    sender_id = int(message.from_user.id)
    chat_id = int(message.chat.id)
    chat_type = str(message.chat.type)
    message_text = str(message.text or '')
    message_type = message.content_type
    session = SessionAgent()
    
    if chat_type == 'supergroup':
        try:
            thread_id = int(message.reply_to_message.message_thread_id)
        except:
            thread_id = 'General'
    elif chat_type == 'private':
        thread_id = 'Private'
    
    bb.add(f'{chat_id}.{thread_id} | {sender_id}',
           f'{message_text} | {message_type}')
    
    sender_data = get_account(sender_id, 'telegram')
    history = _add_to_chat_history(chat_id, thread_id, sender_id, message_text)
    session_prediction = session_ia.predict(message_text)
    
    if thread_id == 'Private':
        if sender_data['ban'] == 2:
            bot.send_message(
                chat_id, 'Извини, ты был заблокирован. Мне запретили с тобой общаться :(')
            return
    
        if int(sender_data['verify']) < v_code:
            verification(sender_id, message_text)
            return
    
        if session_prediction == 'need_session' and sender_data['status'] == 'stable':
        
            if sender_data['ban'] == 1:
                bot.send_message(
                    chat_id, 'Извини, ты был заблокирован оператором. Ты не можешь его вызвать. Придется решать проблему со мной')
                return
            
            if len(history.keys()) <= 8:
                bot.send_message(
                    chat_id, 'Давай сначала я попробую тебе помочь) С каким вопросом ты пришел и/или какая у тебя проблема?')
                return

            if datetime.datetime.now().weekday() in [5, 6] or (datetime.datetime.now().hour >= 19 and datetime.datetime.now().weekday() == 4):
                answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются\nОтвет оператора последует в понедельник с 10:00 до 19:00 по МСК. Желаем хороших выходных!'
            elif (datetime.datetime.now().hour < 10 or datetime.datetime.now().hour >= 19) and (datetime.datetime.now().weekday() not in [5, 6]):
                answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются\nОтвет оператора последует завтра с 10.00 до 19.00'
            else:
                answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются'
                
            session.create_session(sender_id)
            # keyboard = types.InlineKeyboardMarkup(row_width=1)
            # button1 = types.InlineKeyboardButton(text="🔔 Позвать оператора", 
            #                                     callback_data=f'need_session')
            # keyboard.add(button1)

            bot.send_message(chat_id, answer, message_thread_id=thread_id)
            return

        if sender_data['status'] in ['session', 'waiting']:
            session.to_session_send(sender_id, message)
            return
        
        if cd.cooldown_check(sender_id, 'question_ai', 15):
            left = cd.cooldown_check(sender_id, 'question_ai', 15)['seconds']
            bot.send_message(
                chat_id, f'Я ищу ответ на твой прошлый вопрос, пожалуйста подожди...\nВернусь через {left} секунд')
            return
        
        bot.send_chat_action(message.chat.id, 'typing', 15)
    
        answer = await hype.ai_response(
            message_text, sender_id) if message_type == 'text' else 'К сожалению я не имею работать с файлами :('
        
        _add_to_chat_history(chat_id, thread_id, 'BOT', answer)
        
        # print(history)
        
        verdict = consultation_tester.predict(answer)
        if verdict == 'need_consultation':
            message_id = list(history.keys())[-1]
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            button1 = types.InlineKeyboardButton(
                text="🤝 Дать ответ", callback_data=f'consultation:{message_id}')
            keyboard.add(button1)
            
            bot.send_message(5776829003, f'Я не смог найти ответ на вопрос клиента:\n\n {message_text}\n\nЕсли это важный вопрос, нажми на кнопку и напиши верный ответ ;)', reply_markup=keyboard)
              
        bot.send_message(chat_id, answer, message_thread_id=thread_id)
    
    elif chat_id in [main_chat_kz, main_chat_rus] and thread_id != 'General':
        client_id = session.accept_session(sender_id, thread_id) # по ID сессии возвращает соответствующего пользователя

        if client_id:
            session.to_client_send(sender_id, client_id, message)
        else:
            bot.send_message(
                chat_id,
                'Сессия не активна или не найдена!',
                message_thread_id=thread_id)
        return


async def async_handler_old(message):
    sender_id = int(message.from_user.id)
    chat_id = int(message.chat.id)
    chat_type = str(message.chat.type)
    message_text = str(message.text or '')
    message_type = message.content_type
    session = SessionAgent()
    
    if chat_type == 'supergroup':
        try:
            thread_id = int(message.reply_to_message.message_thread_id)
        except:
            thread_id = 'General'
    elif chat_type == 'private':
        thread_id = 'Private'
    
    bb.add(f'{chat_id}.{thread_id} | {sender_id}',
           f'{message_text} | {message_type}')
    
    sender_data = get_account(sender_id, 'telegram')
    history = _add_to_chat_history(chat_id, thread_id, sender_id, message_text)
    #print(history)
    
    if sender_data['ban'] == 2:
        bot.send_message(
            chat_id, 'Извини, ты был заблокирован. Мне запретили с тобой общаться :(')
        return
    
    if int(sender_data['verify']) < v_code and thread_id == 'Private':
        verification(sender_id, message_text)
        return
    
    session_prediction = session_ia.predict(message_text)
    
    if session_prediction == 'need_session' and thread_id == 'Private' and sender_data['status'] == 'stable':
    
        if sender_data['ban'] == 1:
            bot.send_message(
                chat_id, 'Извини, ты был заблокирован оператором. Ты не можешь его вызвать. Придется решать проблему со мной')
            return
        
        if len(history.keys()) <= 8:
            bot.send_message(
                chat_id, 'Давай сначала я попробую тебе помочь) С каким вопросом ты пришел и/или какая у тебя проблема?')
            return

        if datetime.datetime.now().weekday() in [5, 6] or (datetime.datetime.now().hour >= 19 and datetime.datetime.now().weekday() == 4):
            answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются\nОтвет оператора последует в понедельник с 10:00 до 19:00 по МСК. Желаем хороших выходных!'
        elif (datetime.datetime.now().hour < 10 or datetime.datetime.now().hour >= 19) and (datetime.datetime.now().weekday() not in [5, 6]):
            answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются\nОтвет оператора последует завтра с 10.00 до 19.00'
        else:
            answer = 'Я позвал оператора оператора :) Твои сообщения уже транслируются'
            
        session.create_session(sender_id)
        # keyboard = types.InlineKeyboardMarkup(row_width=1)
        # button1 = types.InlineKeyboardButton(text="🔔 Позвать оператора", 
        #                                     callback_data=f'need_session')
        # keyboard.add(button1)

        bot.send_message(chat_id, answer, message_thread_id=thread_id)
        return
    
    if chat_id in [main_chat_kz, main_chat_rus] and thread_id != 'General':
        client_id = session.accept_session(sender_id, thread_id) # по ID сессии возвращает соответствующего пользователя

        if client_id:
            session.to_client_send(sender_id, client_id, message)
        else:
            bot.send_message(
                chat_id,
                'Сессия не активна или не найдена!',
                message_thread_id=thread_id)
        return
    elif sender_data['status'] in ['session', 'waiting'] and thread_id == 'Private':
        session.to_session_send(sender_id, message)
        return
    
    if cd.cooldown_check(sender_id, 'question_ai', 15):
        left = cd.cooldown_check(sender_id, 'question_ai', 15)['seconds']
        bot.send_message(
            chat_id, f'Я ищу ответ на твой прошлый вопрос, пожалуйста подожди...\nВернусь через {left} секунд')
        return
    
    if thread_id != 'Private':
        return
    
    bot.send_chat_action(message.chat.id, 'typing', 15)
    
    answer = await hype.ai_response(
        message_text, sender_id) if message_type == 'text' else 'К сожалению я не имею работать с файлами :('
    
    _add_to_chat_history(chat_id, thread_id, 'BOT', answer)
    
    bot.send_message(chat_id, answer, message_thread_id=thread_id)


def start_telegram_bot():
    async_runner.start()
    while True:
        print('Telegram бот запущен')
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except requests.exceptions.ReadTimeout:
            print('Сервер не отвечает...')
            time.sleep(5)
        except Exception as e:
            bb.add('telegram', f'Error: {e}')
            
if __name__ == '__main__':
    start_telegram_bot()


# Hyperion Repeat >>> екатеринбург — пн-пт 12:00 - 17:00.