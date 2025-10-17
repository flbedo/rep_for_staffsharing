import easydata2 as ed
from pathlib import Path

db_name = 'config'
db_path = Path(f'{db_name}.json')
if not db_path.exists():
    ed.create_database(db_name)
    print(f'{db_name} file was created')

def get_config():
    data = {}
    for id in ed.ids(db_name):
        data[id] = ed.get_id_data(db_name, id)
    return data

