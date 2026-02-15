from gspread import Client, Spreadsheet, Worksheet, service_account, exceptions
from typing import List, Dict
from functools import lru_cache

class GoogleSheets:
    def __init__(self, table_link: str, service_account_file_path: str):
        self.client = self._client_init_json(service_account_file_path)
        self.table = self._get_table_by_url(self.client, table_link)
        
    def _client_init_json(self, service_account_file_path) -> Client:
        """Создание клиента для работы с Google Sheets."""
        return service_account(filename=service_account_file_path)


    def _get_table_by_url(self, client: Client, table_url):
        """Получение таблицы из Google Sheets по ссылке."""
        return client.open_by_url(table_url)
    
    def _get_worksheet_info(self) -> dict:
        """Возвращает количество листов в таблице и их названия."""
        worksheets = self.table.worksheets()
        worksheet_info = {
            "count": len(worksheets),
            "names": [worksheet.title for worksheet in worksheets]
        }
        return worksheet_info

    # def _extract_data_from_sheet(self, table: Spreadsheet, sheet_name: str) -> List[Dict]:
    #     """
    #     Извлекает данные из указанного листа таблицы Google Sheets и возвращает список словарей.

    #     :param table: Объект таблицы Google Sheets (Spreadsheet).
    #     :param sheet_name: Название листа в таблице.
    #     :return: Список словарей, представляющих данные из таблицы.
    #     """
    #     worksheet = table.worksheet(sheet_name)
    #     rows = worksheet.get_all_records()
    #     return rows
    
    def _extract_data_from_sheet(self, table: Spreadsheet, sheet_name: str) -> List[Dict]:
        """
        Извлекает данные из указанного листа таблицы Google Sheets и возвращает список словарей.

        :param table: Объект таблицы Google Sheets (Spreadsheet).
        :param sheet_name: Название листа в таблице.
        :return: Список словарей, представляющих данные из таблицы.
        """
        worksheet = table.worksheet(sheet_name)
        
        headers = worksheet.row_values(1)  # Первая строка считается заголовками
        rows = worksheet.get_all_values()[1:]  # Начинаем считывать с второй строки
        
        max_row_len = max([len(line) for line in rows])
        if len(headers) < max_row_len:
            headers.extend([''] * (max_row_len - len(headers)))

        data = []
        
        for row in rows:
            try:
                row_dict = {headers[i]: value for i, value in enumerate(row)}
                data.append(row_dict)
            except:
                print(f'Ошибка на линии {row}')

        return data

    def get_item_by_line(self, sheet_name, line, item):
        """
        Извлекает данные из указанного листа, столбца и ряда.

        :param sheet_name: Название листа в таблице.
        :param id: Номер строки.
        :param item: Название столбца.
        :return: Ячейка таблицы.
        """
            
        # if sheet_name not in sheets_names:
        #     print('Ошибка! Нет листа с таким названием!')
        #     print('Список листов:', {*sheets_names})
        #     return
        
        data = self._extract_data_from_sheet(self.table, sheet_name)
        
        return data[int(line)-1][item]
    
    def get_line_by_item(self, sheet_name, item, value):
        """
        Извлекает номер(-a) строки из указанного листа таблицы Google Sheets по имеющейся ячейке.

        :param sheet_name: Название листа в таблице.
        :param item: Название столбца.
        :param value: Значение ячейки.
        :return: Номер(-а) линий.
        """
        
        data = self._extract_data_from_sheet(self.table, sheet_name)
        result = []
        result.extend(i+1 for i, row in enumerate(data) if row[item] == value)
        return result
    
    def get_list_of_items(self, sheet_name):
        return list(self._extract_data_from_sheet(self.table, sheet_name)[0].keys())

        