import numpy as np
import faiss
import time
# from pygments import highlight
from sentence_transformers import SentenceTransformer
# from transformers import pipeline
import re
import os
import easydata3 as ed
import localcd as cd
from pathlib import Path
from tabulate import tabulate
from functools import lru_cache
import concurrent.futures
import asyncio
import datetime

# import xgb

from sklearn.metrics.pairwise import cosine_similarity

from transformers import pipeline, T5ForConditionalGeneration, T5Tokenizer, AutoModelForCausalLM, AutoTokenizer
# import torch

# from llama_cpp import Llama
import time

import os
import re
import time
import faiss
import numpy as np
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# import subprocess
from scipy.spatial.distance import cdist
from yandex_cloud_ml_sdk import YCloudML
from langchain_core.messages import AIMessage, HumanMessage
# import requests
import numpy as np
from yandex_cloud_ml_sdk.auth import APIKeyAuth
import easydata3 as ed
import bb
import pytz
from pathlib import Path
from config import get_config

import staffsharing

yandex_folder_id = get_config().get('yandex_folder_id')
yandex_api_key = get_config().get('yandex_api_key')

class LLM:
    def __init__(self, model_size='balanced'):
        """
        Инициализация эффективной GGUF-модели
        :param model_size: 'fast' (быстрая), 'balanced' (оптимум), 'yandexgpt' (качество)
        """
        self.model_size = model_size
        self.model = None
        self.model_paths = {
            'fast': "deepseek-coder-1.3b-instruct.Q8_0.gguf",
            'russian': 'saiga_nemo_12b.Q3_K_M.gguf',
            'balanced': "stealth-v1.3.Q4_K_M.gguf",
            'yandexgpt-lite': "yandex-cloud-model",
            'yandexgpt': "yandex-cloud-model",
        }
        self.sdk = YCloudML(folder_id=yandex_folder_id, auth=APIKeyAuth(
            yandex_api_key))
        self.load_model()

    def load_model(self):
        """Загрузка выбранной GGUF-модели"""

        if self.model_size not in self.model_paths.keys():
            print(
                f'Модель {self.model_size} не найдена или не поддерживается!')
            return

        self.model_path = self.model_paths[self.model_size]
        print(f"Загрузка модели: {self.model_path}")

        if self.model_path == 'yandex-cloud-model':
            self.model = self.sdk.models.completions(
                self.model_size).configure(temperature=0.5, max_tokens=1000)
            return

        raise ValueError('GGUF модели не поддерживаются на сервере')
    
        # n_gpu_layers = 0
        # n_ctx = 2048

        # self.model = Llama(
        #     model_path=self.model_path,
        #     n_ctx=n_ctx,
        #     n_gpu_layers=n_gpu_layers,
        #     n_threads=6,
        #     n_batch=512,
        #     verbose=False
        # )

    def generate(self, query: str, context: str, max_tokens=1024, 
                system_prompt=None, strict_mode=True) -> str:
        
        # Escape HTML-символов для безопасности
        # context = escape(context)
        # query = escape(query)
        
        # Fallback для пустого контекста
        # if not context.strip():
        #     return "Информация не найдена"
        
        if not system_prompt:
            base_rules = '''Ты — Хайпи, поддержка. Отвечай ТОЛЬКО по контексту!
            - Никаких приветствий
            - Обращение на "ты"
            - Ответ 1-2 предложения'''
            
            system_prompt = f"{base_rules}\n- Если ответа нет: 'Информация не найдена'" if strict_mode else base_rules

        # Yandex Cloud
        if self.model_path == 'yandex-cloud-model':
            prompt = [{'role': 'system', 'text': system_prompt},
                    {'role': 'user', 'text': f'Контекст: {context}\nВопрос: {query}'}]
            try:
                output_obj = self.model.run(prompt)
                return output_obj[0].text
            except Exception as e:
                return f"Ошибка генерации: {str(e)}"

        # Локальные модели
        full_prompt = f"""<|im_start|>system
        {system_prompt}<|im_end|>
        <|im_start|>user
        Контекст: {context}
        Вопрос: {query}<|im_end|>
        <|im_start|>assistant"""
        
        params = {
            'max_tokens': max_tokens,
            'temperature': 0.1,
            'top_p': 0.95,
            'stop': ["</s>", "<s>", "###"],
            'echo': False
        }
        
        try:
            start_time = time.time()
            output = self.model(full_prompt, **params)
            gen_time = time.time() - start_time
            
            print(f"Генерация ({self.model_size}): {gen_time:.1f} сек")
            return output['choices'][0]['text'].strip()
        
        except Exception as e:
            print(f"Ошибка генерации: {str(e)}")
            return "Ошибка обработки запроса"


class TextSearchEngine:
    """
    Класс для поиска текстовых фрагментов с использованием эмбеддингов и индекса FAISS.

    Атрибуты:
        file_path (str): Путь к исходному текстовому файлу.
        chunk_size (int): Размер фрагментов текста при разбиении.
        model (SentenceTransformer): Модель для генерации эмбеддингов.
        dim (int): Размерность векторов эмбеддингов.
        index (faiss.Index): Индекс для быстрого поиска.
        chunks (List[str]): Список текстовых фрагментов.
    """

    def __init__(self, file_path='faq.txt', model_name='sentence-transformers/all-MiniLM-L6-v2', chunks=None):
        """
        Инициализация поискового движка.

        Args:
            file_path (str): Путь к текстовому файлу.
            model_name (str, optional): Название модели SentenceTransformer. По умолчанию 'sentence-transformers/all-MiniLM-L6-v2'.
        """
        self.file_path = file_path

        file_size = os.path.getsize(file_path) / 1024  # KB
        self.chunk_size = max(100, min(700, int(file_size / 10)))

        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()
        self.index = None
        self.chunks = chunks or []

        self.bm25 = None
        self.tokenized_chunks = []
        self.stop_words = set(stopwords.words(
            'russian') + stopwords.words('english'))

        if not chunks: self._chunking()

        self._build_index()
        self._init_bm25()

    def _chunking(self):
        """
        Загрузка и предварительная обработка текстового файла.

        Разбивает текст на фрагменты заданного размера.
        """
        with open(self.file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        words = text.split()
        self.chunks = [
            ' '.join(words[i:i + self.chunk_size])
            for i in range(0, len(words), self.chunk_size)
        ]

    def _build_index(self):
        """
        Создание индекса FAISS на основе эмбеддингов фрагментов текста.

        Адаптирует параметры индекса в зависимости от объема данных.
        """
        embeddings = self.model.encode(
            self.chunks, show_progress_bar=False, batch_size=32)
        faiss.normalize_L2(embeddings)
        n_vectors = len(embeddings)

        if n_vectors < 1000:
            self.index = faiss.IndexFlatIP(self.dim)
        else:
            nlist = min(100, max(4, int(np.sqrt(n_vectors))))
            m = min(16, self.dim // 4)
            
            # Проверяем достаточно ли данных для обучения IVF
            if n_vectors < nlist * 39:  # Минимальное требование Faiss
                print(f"Недостаточно данных для IVF. Используем IndexFlatIP")
                self.index = faiss.IndexFlatIP(self.dim)
            else:
                print(f"Используем оптимизированный индекс (IVF{nlist} + PQ{m}x8)")
                quantizer = faiss.IndexFlatIP(self.dim)
                self.index = faiss.IndexIVFPQ(quantizer, self.dim, nlist, m, 8)

                # Обучение только если данных достаточно
                train_size = min(max(100, nlist * 39), n_vectors)
                if train_size >= nlist * 39:
                    print(f"Обучение на {train_size} векторах...")
                    self.index.train(embeddings[:train_size])
                else:
                    print("Недостаточно данных для обучения IVF. Используем IndexFlatIP")
                    self.index = faiss.IndexFlatIP(self.dim)
        

        self.index.add(embeddings)

    def _preprocess_text(self, text):
        """Токенизация и очистка текста для BM25."""
        tokens = word_tokenize(text.lower())
        return [token for token in tokens if token.isalnum() and token not in self.stop_words]

    def _init_bm25(self):
        # Токенизация фрагментов с предобработкой
        self.tokenized_chunks = [self._preprocess_text(
            chunk) for chunk in self.chunks]
        self.bm25 = BM25Okapi(self.tokenized_chunks)

    def bm25_search(self, query, k=5):

        tokenized_query = self._preprocess_text(query)

        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:k]

        # Формирование результатов
        results = []
        for idx in top_indices:
            result = {
                'text': self.chunks[idx],
                'score': scores[idx],
                'position': idx
            }
        return results

    def faiss_search(self, query, k=5):
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)

        if isinstance(self.index, faiss.IndexIVFPQ):
            self.index.nprobe = min(10, self.index.nlist // 2)

        distances, indices = self.index.search(query_embedding, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0:
                results.append({
                    'text': self.chunks[idx],
                    'score': distances[0][i],
                    'position': idx
                })
        return results

    def vector_similarity(self, text1: str, text2: str) -> float:
        """
        Вычисляет косинусное сходство между двумя текстами
        """
        embeddings = self.model.encode([text1, text2])
        
        similarity = cosine_similarity(
            [embeddings[0]],
            [embeddings[1]]
        )
        
        return similarity[0][0]


    def search(self, query, k=5, alpha=0.4):

        start_time = time.time()

        tokenized_query = self._preprocess_text(query)

        bm25_scores = self.bm25.get_scores(tokenized_query)

        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)

        if isinstance(self.index, faiss.IndexIVFPQ):
            self.index.nprobe = min(10, self.index.nlist // 2)

        faiss_scores, faiss_indices = self.index.search(
            query_embedding, len(self.chunks))
        faiss_scores = faiss_scores.flatten()

        bm25_scores_norm = (bm25_scores - np.min(bm25_scores)) / \
            (np.max(bm25_scores) - np.min(bm25_scores) + 1e-9)
        faiss_scores_norm = (faiss_scores - np.min(faiss_scores)) / \
            (np.max(faiss_scores) - np.min(faiss_scores) + 1e-9)

        combined_scores = alpha * bm25_scores_norm + \
            (1 - alpha) * faiss_scores_norm

        top_indices = np.argsort(combined_scores)[::-1][:k]

        search_time = time.time() - start_time
        results = []
        for idx in top_indices:
            results.append({
                'text': self.chunks[idx],
                'score': combined_scores[idx],
                'position': idx,
                'bm25_score': bm25_scores[idx],
                'faiss_score': faiss_scores[idx],
                'time': search_time
            })
        return results


class RelpSearchSystem(TextSearchEngine):
    def __init__(self, db_name='faq', info_base='faq'):

        self.db = db_name
        db_path = Path(f'{self.db}.db')
        if not db_path.exists():
            ed.create_database(self.db)
            ed.give_item_data(self.db, 'system', 'last_id', 0)
            print('Создан файл FAQ!')

        self.qa = {}

        # self.llm_balanced = LLM('balanced')
        self.llm_quality = LLM('yandexgpt-lite')

        super().__init__(f'{info_base}.txt')

        if ed.get_item_data(self.db, 'system', 'last_id') == 0:
            self._make_qa_pairs()

        self._faq_chunking()
        self._build_index()
        self._init_bm25()
    
    def _get_qa_pairs(self):

        for id in ed.ids(self.db):
            # q = ed.get_item_data(self.db, id, 'question')
            # a = ed.get_item_data(self.db, id, 'answer')
            q = ed.get_item_data(self.db, id, 'contain') or ed.get_item_data(self.db, id, 'question')
            a = ed.get_item_data(self.db, id, 'response') or ed.get_item_data(self.db, id, 'answer')

            self.qa[q] = a

    def _analize_chunk(self, chunk):
        llm_answer = self.llm_quality.generate(
            'Сгенерируй вопросы и ответы: ',
            chunk,
            system_prompt=f'''Ты — эксперт по извлечению информации. На основе предоставленного контекста:
        1. Сгенерируй 8 разнообразных вопросов, на которые можно ответить, используя только данный контекст
        2. Для каждого вопроса дай точный ответ, дословно цитируя или перефразируя контекст
        3. Делай несколько вариантов вопросов, не меняя 
        3. Соблюдай строгий формат: "Вопрос: ...\nОтвет: ..."

        Правила:
        - Запрещено добавлять информацию, отсутствующую в контексте
        - Если контекст не содержит ответа - пропусти вопрос
        - Используй только факты из контекста без интерпретаций
        - Сохраняй оригинальные термины и цифровые значения
        - Запрещено добавлять повторяющиеся вопросы
        - Начинай сразу с первого вопроса, без вводных фраз
        - Выдели числовые параметры в отдельные вопросы (цены, сроки, размеры)
        - Приоритет: уникальные аспекты контекста
        - Запрещено упоминать контекст или источник информации'''
        )

        qa_list = llm_answer.split('\n\n')
        for qa_item in qa_list:
            qa_item = qa_item.replace('Ответ:', '').replace('Вопрос:', '')
            q, a = qa_item.split('\n')

            last_id = int(ed.get_item_data(self.db, 'system', 'last_id'))
            ed.give_item_data(self.db, last_id+1, 'question', q)
            ed.give_item_data(self.db, last_id+1, 'answer', a)
            ed.give_item_data(self.db, 'system', 'last_id', last_id+1)

    def _make_qa_pairs(self):

        ed.give_item_data(self.db, 'system', 'last_id', 0)

        self._chunking()

        self._build_index()
        self._init_bm25()

        for chunk in self.chunks:
            self._analize_chunk(chunk)

        self._sync_sessions_and_faq()

    def _faq_chunking(self):
        self._get_qa_pairs()
        self.chunks = list(map(str, self.qa.keys()))

    def relp_search(self, query, k=5, alpha=0.4):
        elements = self.search(query, k, alpha)
        self._get_qa_pairs()
        result = []

        for element in elements:
            result.append({
                'text': self.qa[element['text']],
                'score': element['score'],
                'position': element['position'],
                'bm25_score': element['bm25_score'],
                'faiss_score': element['faiss_score'],
                'time': element["time"],
            })

        return result

    def _sync_sessions_and_faq(self):

        for id in ed.ids('users'):
            if q := ed.get_item_data('users', id, 'question'):
                a = ed.get_item_data('users', id, 'answer')
                last_id = int(ed.get_item_data(self.db, 'system', 'last_id'))
                ed.give_item_data(self.db, last_id+1, 'question', q)
                ed.give_item_data(self.db, last_id+1, 'answer', a)
                ed.give_item_data(self.db, 'system', 'last_id', last_id+1)

class Hyperion:
    def __init__(self, info_base='faq'):
        
        self.rss = RelpSearchSystem()
        self.rss_cache = RelpSearchSystem('ai')
        self.tse = TextSearchEngine(f'{info_base}.txt')
        
        self.llm = self.rss.llm_quality
        self.sdk = YCloudML(folder_id=yandex_folder_id, auth=APIKeyAuth(
            yandex_api_key))
        
        self.staffsharing_rental_place = staffsharing.RentalPlace()
        
    async def fast_ai(self, system, message, context=''):
        if not message:
            return None
        
        result = await asyncio.to_thread(
            self.llm.generate, message, context, system_prompt=system
        )
        return result
    
    def _chat_history(self, chat_id, user_id=0, message=0, message_type='text'):
        CHATS = 'chats'
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

    def analize(self, history, model='yandexgpt-lite'):

        model = self.sdk.models.completions(model)
        model = model.configure(temperature=1, max_tokens=1000)
        model_lc = model.langchain(model_type="chat", timeout=60)

        langchain = []
        for msg in sorted(history.keys(), key=int):
            if history[msg]['message'] == '':
                continue
            if history[msg]['user_id'] != 'BOT':
                langchain.append(HumanMessage(str(history[msg]['message'])))
            if history[msg]['user_id'] == 'BOT':
                langchain.append(AIMessage(str(history[msg]['message'])))

        langchain.append(HumanMessage(f'''Вдумчиво прочитай и проанализируй весь чат. 
        Определи основную основной вопрос пользователя, продумай, в чем могла быть проблема. 
        На основе ответов бота сформулируй полезный, краткий и точный ответ.
        Вопрос перефразируй и распространи.
        Ответ дай в вормате: "Вопрос: [вопрос]?\nОтвет: [ответ].".
        '''))

        try:
            langchain_analize = model_lc.invoke(langchain).content
            langchain_analize = langchain_analize.lower()
            for s in ['вопрос: ', 'ответ: ', '[', ']']:
                langchain_analize = langchain_analize.replace(s, '')
            langchain_analize = langchain_analize.split('\n') if len(
                langchain_analize.split('\n')) > 1 else ['Ошибка', 'Ошибка']
        except Exception:
            langchain_analize = ['Не удалось проанализировать чат :(', '']

        return langchain_analize
        
    def _get_langchain(self, history):
        langchain = []
        for msg in list(sorted(history.keys(), key=int))[-6:]:
            
            author = history[msg]['user_id']
            text = str(history[msg]["message"])
            
            if text == '':
                continue
            if author != 'BOT':
                langchain.append(HumanMessage(text))
            if author == 'BOT':
                langchain.append(AIMessage(text))
        return langchain
    
    def _get_last_messages(self, history):
        user = []
        bot = []
        for msg in list(sorted(history.keys(), key=int))[-6:]:
            
            author = history[msg]['user_id']
            text = str(history[msg]["message"])
            
            if text == '':
                continue
            if author != 'BOT':
                user.append(text)
            if author == 'BOT':
                bot.append(text)
        return user, bot
    
    async def context_analysis(self, question, history):

        model = self.sdk.models.completions('yandexgpt-lite')
        model = model.configure(temperature=0.5, max_tokens=1000)
        model_lc = model.langchain(model_type="chat", timeout=60)

        langchain = self._get_langchain(history)
        bot_responses = self._get_last_messages(history)[1]

        # question_about = await self.fast_ai(
        #     'Ты должен определить узкую тему вопроса. В ответа напиши только тему. Пример: "Вы ставите иот модуль?" -> IoT', question)

        repeat_test = await self.fast_ai('''Ты — система проверки фактов. Проанализируй предоставленный контекст и вопрос пользователя.
    # Инструкции:
    1. Ответь строго на основе предоставленного контекста.
    2. Если в контексте **точно и однозначно** содержится ответ на вопрос — напиши «True» и приведи дословную цитату из контекста в кавычках.
    3. Если в контексте нет прямого ответа на вопрос — напиши только «False».''', question, context='\n'.join(bot_responses))

        langchain.append(HumanMessage(question))

        langchain.append(HumanMessage(
            'На основании переписки кратко опиши ситуацию клиента. Четко опиши ситуацию клиента и его основную проблему. Если нет ничего важного - пиши "пусто"'))
        langchain_context = model_lc.invoke(langchain).content
        langchain.pop(-1)

        # print(f'Hyperion Context >>> {langchain_context}')
        # print(f'Hyperion Repeat >>> {langchain_repeat_test.lower()}')

        if 'false' in repeat_test.lower(): return langchain_context, (True, repeat_test.lower())
        elif 'true' in repeat_test.lower(): return langchain_context, (False, repeat_test.lower())
        elif 'false' not in repeat_test.lower(): return langchain_context, (False, repeat_test.lower())
        
    async def _normalize_question(self, context, question):
        system_prompt = 'На основе вопроса клиента и контекста его ситуации, сделай краткий и исчерпывающий вопрос для поиска ответа в базе знаний'

        new_question = await self.fast_ai(system_prompt,question, context=context)
        
        return new_question
    
    async def question_exist(self, question):
        
        verdict = await self.fast_ai('''Ты анализируешь сообщение. 
        Если сообщение содержит четко выраженную проблему или вопрос - напиши "True", а затем вопрос''',
                      question)

        # print(f'Hyperion Question >>> {verdict}')
        
        # c1 = any(word in verdict.lower() for word in [' да ', ' да,', 'да\n', 'да, '])
        # c2 = any(word in verdict.lower() for word in [' нет ', ' нет,', ' нет\n'])
        
        if 'true' in verdict.lower(): return (True, verdict.lower())
        elif 'false' in verdict.lower(): return (False, verdict.lower())
        elif 'true' not in verdict.lower(): return (False, verdict.lower())

    def _get_last_question_id(self, history):
        return sorted(list(history.keys()), key=int)[-1]

    def _get_faq_answer(self, search_response):
        return ''.join(item["text"] + '\n' for item in search_response)

    def _is_blocked_response(self, response):
        f1 = 'https://ya.ru' in response
        f2 = '[' in response
        return f1 or f2
   
    def _standart_sys_prompt(self):
        return '''Ты - Хайпи, агент тех. поддержки и призван помогать пользователям. 
        1. Ответь на вопрос используя исключительно данные из подсказки и контекста.
        2. Найди необходимую часть подсказки, которая содержит необходимую информацию и ответь на вопрос клиента используя данные из подсказки.
        3. Подсказки имеют высший приоритет при решении проблемы клиента. 
        4. Тебе строго запрещено здороваться. 
        5. Ты строго обязан общаться на ты.
        6. Если недостаточно информации в подсказке, то уточни, что ответ может быть не точным и порекомендуй его перефразировать'''
   
    def _add_operator_recomendation(self, pre_response, repeat_test, history):
        system_prompt = self._standart_sys_prompt()

        if not repeat_test and len(history.keys()) > 8:
            response = f'{pre_response}\n\nРекомендую позвать оператора, так как я не могу более точно ответить на данный вопрос'
        else: response = pre_response

        return response
    
    @lru_cache(maxsize=100)
    def _search_by_type(self, query, search_type, k=5):
        """Кэшированный поиск для уменьшения повторных запросов"""
        if search_type == 'TSE':
            return self.tse.search(query, k=k)
        elif search_type == 'RELP8':
            return self.rss.relp_search(query, k=k, alpha=0.8)
        elif search_type == "RELP3":
            return self.rss.relp_search(query, k=k, alpha=0.3)
        elif search_type == 'CACHE':
            return self.rss_cache.relp_search(query, k=k, alpha=0.6)
        return []
    
    def _get_ai_response_lays(self, query, system_prompt, **kwargs):

        if self.staffsharing_rental_place.predict(query) == 'rental_place':
            search_response = self.staffsharing_rental_place.get_data_by_city(kwargs['client_city'])
            faq_answer = search_response
            context = f'''Ситуация: {kwargs['situation']}
            Подсказка: {faq_answer}''' 
            search_type = 'XGB+GH'
            response = self.llm.generate(query=query, context=context, system_prompt=system_prompt, strict_mode=False)
        else:
            search_response = self.tse.search(query)
            faq_answer = self._get_faq_answer(search_response)
            context = f'''Ситуация: {kwargs['situation']}
            Подсказка: {faq_answer}''' 
            search_type = 'TSE'               

            response = self.llm.generate(query=query, context=context, system_prompt=system_prompt, strict_mode=False)
        
        if '<no_info>' in response:
            search_response = self.rss.relp_search(query)
            faq_answer = self._get_faq_answer(search_response)
            context = f'''Ситуация: {kwargs['situation']}
            Подсказка: {faq_answer}'''  
            search_type = 'RELP' 
            response = self.llm.generate(query=query, context=context, system_prompt=system_prompt, strict_mode=False) 
            
        if '<no_info>' in response:
            search_response = self.rss_cache.relp_search(query, 1)
            faq_answer = self._get_faq_answer(search_response)
            context = f'''Ситуация: {kwargs['situation']}
            Подсказка: {faq_answer}'''  
            search_type = 'CACHE' 
            response = self.llm.generate(query=query, context=context, system_prompt=system_prompt, strict_mode=False) 
        
        if '<no_info>' in response:
            response = asyncio.run(self.fast_ai('''Ты агент тех. поддержки и призван помогать пользователям.
            1. Тебе запрещается здороваться с пользователем.
            2. Попробуй ответить на вопрос пользователя 
            3. Уточни, что твой ответ может быть неточен 
            4. Порекомендуй пользователю перефразировать вопрос и дай ему несколько вариантов вопроса''', query))
            search_type = 'NO_SEARCH' 
        
        if 'Ответ: ' in response: response = response.split('Ответ: ')[1]
            
        return response, search_response, search_type
    
    def _get_ai_response(self, query, system_prompt, **kwargs):
        situation = kwargs.get('situation', '')
        client_city = kwargs.get('client_city', 'Москва')
        
        results_gh = [{}]

        if self.staffsharing_rental_place.predict(query) == 'rental_place':
            search_response = self.staffsharing_rental_place.get_data_by_city(client_city)
            # context = f"Ситуация: {situation}\nПодсказка: {search_response}"
            # response = self.llm.generate(
            #     query=query, 
            #     context=context, 
            #     system_prompt=system_prompt, 
            #     strict_mode=False
            # )
            for res in results_gh:
                res['text'] = search_response
                res['score'] = 1.0
                res['source'] = 'gh'

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_tse = executor.submit(self._search_by_type, query, 'TSE', 5)
            future_relp8 = executor.submit(self._search_by_type, query, 'RELP8', 3)
            future_relp3 = executor.submit(self._search_by_type, query, 'RELP3', 5)
            future_cache = executor.submit(self._search_by_type, query, 'CACHE', 1)
            
            results_tse = future_tse.result()
            results_relp8 = future_relp8.result()
            results_relp3 = future_relp3.result()
            results_cache = future_cache.result()
            
            for res in results_tse:
                res['source'] = 'tse'
            for res in results_relp8:
                res['source'] = 'rss8'
            for res in results_relp3:
                res['source'] = 'rss3'
            for res in results_cache:
                res['source'] = 'rss_cache'

        all_results = results_tse + results_relp8 + results_relp3 + results_cache + results_gh
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        top_results = all_results[:5]
        
        search_type = top_results[0]['source']
            
        faq_answer = self._get_faq_answer(top_results)
        context = f"Ситуация: {situation}\nПодсказка: {faq_answer}"
        
        response = self.llm.generate(
            query=query, 
            context=context, 
            system_prompt=system_prompt, 
            strict_mode=False
        )
        
        # if '<no_info>' in response:
        #     response = await self.fast_ai('''Ты агент тех. поддержки аренды электровелосипедов и призван помогать пользователям.
        #     1. Тебе запрещается здороваться с пользователем.
        #     2. Попробуй ответить на вопрос пользователя 
        #     3. Обязательно уточни, что твой ответ может быть неточен
        #     4. Порекомендуй пользователю перефразировать вопрос''', query)
        #     search_type = 'NO_SEARCH'
        
        return response, top_results, search_type
    
    async def ai_response(self, query, sender_id):
        
        start_time = time.time()
        
        sender_data = ed.get_id_data('users', sender_id)
        cd.cooldown_set(sender_id, 'question_ai')

        if int(ed.get_item_data('users', 'system', 'bot')) == 0 and sender_data['role'] != 'admin':
            return 'Бот на тех. обслуживании. Попробуй написать позже :('

        system_prompt = self._standart_sys_prompt()

        history = self._chat_history(sender_id)
        question_id = self._get_last_question_id(history)
        client_name = sender_data['name'] if sender_data['name'] != '' else 'Пользователь'
        client_city = sender_data['city'] if sender_data['city'] != '' else 'Москва'

        question_exist = await self.question_exist(query)
        if not question_exist[0]:
            response = await self.fast_ai('''Ты агент тех. поддержки и призван помогать пользователям.
            Тебе запрещается здороваться с пользователем.
            Ответ дай ввиде обычного сообщения, не внося в него никаких дополнительных данных. 
            Ты строго обязан общаться на ты''', query)
            gen_time = time.time() - start_time

            ai_response_data = {
                'contain': query,
                'question_test': question_exist,
                'response': response,
                'need_time': gen_time
            }

            ed.give_id_data('ai', question_id, ai_response_data)

            if self._is_blocked_response(response):  
                response = 'Извини, запрос был заблокирован по техническим причинам. Попробуй перефразировать запрос!'
                ed.give_item_data('ai', question_id, 'accident', 'true')
            
            bb.add(f'HypeBot #{question_id}', response)
            
            cd.cooldown_drop(sender_id, 'question_ai')
            
            return response

        situation, repeat_test = await self.context_analysis(query, history)
        # query = await self._normalize_question(situation, query)
        
        # print(f'Нормализация запроса: {query}')
        
        response, search_response, search_type = await asyncio.to_thread(
            self._get_ai_response, query, system_prompt, client_city=client_city, situation=situation
        )
        
        # response, search_response, search_type = self._get_ai_response(query, system_prompt, client_city=client_city, situation=situation)
        gen_time = time.time() - start_time
        
        if self._is_blocked_response(response):  
            response = 'Извини, запрос был заблокирован по техническим причинам. Попробуй перефразировать запрос!'
            ed.give_item_data('ai', question_id, 'accident', 'true')
            
        response = self._add_operator_recomendation(response, repeat_test[0], history)


        ai_response_data = {
            'contain': query,
            'context': situation,
            'faq': search_response,
            'search_type': search_type,
            'repeat_test': repeat_test,
            'question_test': question_exist,
            'response': response,
            'need_time': gen_time
        }

        ed.give_id_data('ai', question_id, ai_response_data)
        
        bb.add(f'HypeBot #{question_id}', response)
        
        cd.cooldown_drop(sender_id, 'question_ai')

        return response

class Printer:
    def print_results(self, result):
        # Подготавливаем данные для таблицы
        table_data = []
        for item in result:
            # Форматируем текст (первые 50 символов)
            text = item['text'][:100] + \
                '...' if len(item['text']) > 50 else item['text']

            table_data.append([
                text,
                f"{item['score']:.4f}",
                item['position'],
                f"{item['bm25_score']:.4f}" if 'bm25_score' in item else 'N/A',
                f"{item['faiss_score']:.4f}" if 'faiss_score' in item else 'N/A',
                f"{item['time']:.4f}s"
            ])

        # Заголовки таблицы
        headers = [
            "Text Fragment",
            "Total Score",
            "Position",
            "BM25 Score",
            "FAISS Score",
            "Time"
        ]

        # Вывод таблицы с настройками
        print(tabulate(table_data,
                       headers=headers,
                       # Стиль: fancy_grid, psql, github и др.
                       tablefmt="fancy_grid",
                       maxcolwidths=45,       # Макс. ширина колонки
                       numalign="center",
                       stralign="left"))

    def print_ai_response(self, response, name):
        print(f'{name} >>> ', end='')
        for char in response:
            print(char, end='', flush=True)
            time.sleep(0.02)
        print()
    
    
# @lru_cache(maxsize=100)
# def type_search(query, search_type, k=5):
#     """Кэшированный поиск для уменьшения повторных запросов"""
#     if search_type == 'TSE':
#         return tse.search(query, k=k)
#     elif search_type == 'RELP':
#         return rss.relp_search(query, k=k)
#     elif search_type == 'CACHE':
#         return rss_cache.relp_search(query, k=k, alpha=0.7)
#     return []    
    
if __name__ == "__main__":
    print('Инициализую движки поиска...')
    rss = RelpSearchSystem('faq')
    print('RSS инициализирован!')
    # rss_cache = RelpSearchSystem('ai')
    # print('RSS_Cache инициализирован!')
    # tse = TextSearchEngine(f'faq.txt')
    # print("TSE инициализирован!")
    # hype = Hyperion()
    # print("Hyperion инициализирован!")
    printer = Printer()
    query = ''

    while query != 'exit':
        print('════' * 20)
        query = input(">>> ")
        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     future_tse = executor.submit(type_search, query, 'TSE', 5)
        #     future_relp = executor.submit(type_search, query, 'RELP', 3)
        #     future_cache = executor.submit(type_search, query, 'CACHE', 1)
            
        #     results_tse = future_tse.result()
        #     results_relp = future_relp.result()
        #     results_cache = future_cache.result()
        
        results_relp = rss.relp_search(query, alpha=0.8)
            
        all_results = results_relp
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_results = all_results[:5]
        
        context = ''.join(item["text"] + '\n' for item in all_results)
        
        
        # printer.print_results(results_tse)
        # print('════' * 10)
        printer.print_results(results_relp)
        print('════' * 10)
        # printer.print_results(results_cache)
        # print('════' * 10)
        # printer.print_results(top_results)
        # print('════' * 10)
        
