import easydata2 as ed
import datetime as dt
from pathlib import Path
import time

DB_NAME = 'cd'
db_path = Path(f'{DB_NAME}.json')
if not db_path.exists():
    ed.create_database(DB_NAME)
    print('CD file was created')

def cooldown_check(user, arg: str, cd: int):
    if ed.is_item_exist(DB_NAME, user, arg):
        then = dt.datetime.strptime(ed.get_item_data(DB_NAME, user, arg), "%Y-%m-%d %H:%M:%S.%f")
        now = dt.datetime.now()
        delta = now - then
        if delta.total_seconds() >= cd:
            return False
        else:
            seconds_left = int(str(cd - delta.total_seconds()).split('.')[0])
            days_left = seconds_left // 86400
            seconds_left -= days_left * 86400
            hours_left = seconds_left // 3600
            seconds_left -= hours_left * 3600
            minutes_left = seconds_left // 60
            seconds_left -= minutes_left * 60
            left = {'days': days_left, 'hours': hours_left, 'minutes': minutes_left, 'seconds': seconds_left}
            return left 
    else:
        return False
    
def cooldown_set(user, arg: str):
    if ed.is_id_exist(DB_NAME, user):
        
        ed.give_item_data(DB_NAME, user, arg, str(dt.datetime.now()))

    else:
        ed.give_id_data(DB_NAME, user, {})
        ed.give_item_data(DB_NAME, user, arg, str(dt.datetime.now()))

def cooldown_drop(user, arg: str):
    if ed.is_id_exist(DB_NAME, user):
        ed.give_item_data(DB_NAME, user, arg, '2000-01-01 00:00:00.565852')
    else:
        return False
        
    