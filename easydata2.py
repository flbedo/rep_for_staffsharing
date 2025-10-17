import json
from typing import Any, Union

def create_database(f_name: str) -> None:
    file = f'{f_name}.json'
    
    with open(file, 'w', encoding='utf8') as f:
        json.dump({}, f)

def _read_data(f_name: str) -> dict[str, dict[str, Any]]:
    file = f'{f_name}.json'
    
    with open(file, 'r', encoding="utf8") as f:
        data = json.load(f)
        
    return data

def _write_data(f_name, value: dict[str, dict[str, Any]]) -> None:
    file = f'{f_name}.json'
    
    with open(file, 'w', encoding='utf8') as f:
        json.dump(value, f, indent=4)

def get_id_data(f_name: str, id: str) -> Union[dict[str, Any], None]:
    
    data = _read_data(f_name)
    
    return data.get(str(id), None)

def get_item_data(f_name: str, id: str, item: str) -> Any:
    
    data = _read_data(f_name)

    user_data = data.get(str(id), None)
    
    if not user_data:
        return
        
    return user_data.get(str(item), None)

def give_id_data(f_name: str, id: str, value: dict[str, dict[str, Any]]) -> None:
    
    data = _read_data(f_name)
    
    data[str(id)] = value
    
    _write_data(f_name, data)
    
    return value
    
def give_item_data(f_name: str, id: str, item: str, value: Any) -> None:
    
    data = _read_data(f_name)
    
    user_data = data.get(str(id), None)

    if user_data == None and id not in data:
        give_id_data(f_name, str(id), {})
        user_data = {}

    user_data[str(item)] = value 
    
    data[str(id)] = user_data

    _write_data(f_name, data)
    
    return value

def give_all_item_data(f_name: str, item: str, value: Any) -> None:
    
    data = _read_data(f_name)

    # ВНИМАНИЕ! Команда не меняет первого пользователя!
    
    for user in range(1, len(data) + 1):
        give_item_data(f_name, data[user], item, value)
        
    return value
        
def delete_id_data(f_name: str, id: str) -> None:
    data = _read_data(f_name)

    if not id in data:
        return

    del data[id]
    _write_data(f_name, data)
    
    return id

def extremum_item_data(f_name: str, item: str, max_or_min: str) -> Any:
    data = _read_data(f_name)

    extremum_value = {'max': '0', 'min': str(11*9*(10*100))}[max_or_min]

    for id in data:

        value = data[id][item]


        if str(value).isdigit():
            extremum_value = int(extremum_value)
            value = int(value)

        if max_or_min == 'max':
            extremum_value = max(value, extremum_value)
        elif max_or_min == 'min':
            extremum_value = min(value, extremum_value)



    return extremum_value


def ids(f_name: str) -> dict[str, Any]:
    
    data = _read_data(f_name)
    ids = []
    
    for id in data:
        
        ids.append(id)
    
    return ids
    
def is_id_exist(f_name: str, id: str):
    
    if get_id_data(f_name, id) != None:
        return True
    
    else:
        return False
    
def is_item_exist(f_name: str, id: str, item: str):
    
    if get_item_data(f_name, id, item) != None:
        return True
    
    else:
        return False


