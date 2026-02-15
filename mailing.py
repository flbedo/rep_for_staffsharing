import requests
import time
import asyncio
    
    
base_url = 'https://api3.sms-agent.ru/v2.0/'

class Sender_SMS():
    def __init__(self, login: str, password: str):
        self.login = login
        self.password = password
    async def check_status(self, id):
        status_decoder = ['В очереди', 'Передано оператору связи', 'Доставлено', 'Не доставлено', 'Истек срок "жизни" сообщения', 'Недопустимое значение ID', 'ID не найдено']

        params_status = {
            'login': self.login,
            'pass': self.password,
            'act': 'status',
            'id': id
        }
        
        response_status = int(requests.get(base_url, params=params_status).text)
        return status_decoder[response_status]
    
    async def send(self, numbers: list, text: str):
        params = {
            'login': self.login,
            'pass': self.password,
            'act': 'send',
            'from': 'SMSINFO', # Нужно проверить на счет имен :(
            'to': numbers,
            'text': text
        }
        response = requests.get(base_url, params=params)
        if response.status_code != 200: raise Exception('Не удалось связаться с сервером!')
        sms_ids = response.text.split(', ')
        
        try: map(int, sms_ids)
        except: raise Exception('Ошибка запроса на сервер!')
        
        await asyncio.sleep(3)

        if len(sms_ids) != len(numbers): raise Exception('Кол-во статусов не совпадает с кол-вом номеров рассылки!')
        
        success = []
        unsuccess = []
        waiting = []
        error = []
        base = {}
        
        for i in range(len(sms_ids)): 
            base[numbers[i]] = sms_ids[i]
        
        for number, id in base.items():
            status = await self.check_status(id)
            
            if status == 'Доставлено': success.append(number)
            elif status == 'Не доставлено': unsuccess.append(number)
            elif status == 'В очереди' or status == 'Передано оператору связи': waiting.append(number)
            else: error.append(number)
        
        if len(waiting) != 0: 
            asyncio.sleep(3)
            for number in waiting:
                status = await self.check_status(base[number])
                
                if status == 'Доставлено': success.append(number)
                elif status == 'Не доставлено': unsuccess.append(number)
                else: error.append(number)
        
        return success, unsuccess, error
            
            
#   логин:  Staffsharing
#   пароль:  EiSJszN2tSrPUL!