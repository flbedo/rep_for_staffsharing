import json
import datetime as dt
from pathlib import Path
import time
import pytz
import psutil

DB_NAME = 'bb'
peak = 0

def log_memory():
    global peak
    current = psutil.Process().memory_info().rss
    peak = max(peak, current)
    return current // 1024**2, peak // 1024**2

    
def add(user, arg: str, db=DB_NAME):
    cur, peak = log_memory()

    db_path = Path(f'{db}.txt')
    if not db_path.exists():
        with open(db + '.txt', 'w') as f:
            f.write('')
            print(f'{db} file was created')
    now = dt.datetime.now(pytz.timezone("Europe/Moscow")).strftime('%H:%M %d.%m')
    print(f'{now}: {user} - {arg} ({cur}MB, {peak}MB)')
    try:
        with open('bb.txt', 'r', encoding='utf-8') as f:
            data = f.read()
    except UnicodeDecodeError:
        with open('bb.txt', 'r', encoding='ISO-8859-1') as f:
            data = f.read()
    with open(db + '.txt', 'w', encoding='utf-8') as f:
        f.write(data + f'{now}: {user} - {arg}\n')