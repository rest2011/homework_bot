import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

NO_TOKEN_MESSAGE = ('Программа принудительно остановлена. '
                    'Отсутствует обязательная переменная окружения: {token}')
TELEGRAM_MESSAGE_SENT = 'Сообщение в Telegram отправлено: {message}'
TELEGRAM_MESSAGE_NOT_SENT = ('Сообщение в Telegram не отправлено: {message},'
                             '{telegram_error}')
REQUEST_ERROR = ('Код ответа API (RequestException):'
                 '{request_error}. Переданы параметры {parameters}')
STATUS_CODE_200_ERROR = ('Код ответа API равен {status_code},'
                         'а не 200. Переданы параметры {parameters}')
API_DICT_ERROR = 'Ожидаемый тип данных - словарь, получен {data_type}'
API_LIST_ERROR = 'Ожидаемый тип данных - список, получен {data_type}'
NO_KEY_ERROR = 'Отсутствует ключ {key}.'
EMPTY_VALUE_ERROR = 'Отсутствует значение {value}'
STATUS_NOT_IN_HOMEWORK_VERDICTS = ('Новый статус {value}. '
                                   'Нужно обновить словарь HOMEWORK_VERDICTS')
CHANGE_HOMEWORK_STATUS = ('Изменился статус проверки работы '
                          '"{homework_name}". {verdict}')
MAIN_EXCEPTION_ERROR = 'Сбой в работе программы: {error}'
RESPONSE_ERROR = ('В ключе ответа {response_json} есть ошибка {response_error}'
                  '. Переданы параметры {parameters}')
NOCHANGE_HOMEWORK_STATUS = 'Статус домашней работы не изменился'

logger = logging.getLogger(__name__)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


class ResponseException(Exception):
    """Ошибка в ответе."""


class StatusNotChange(Exception):
    """Статус домашней работы не изменился."""


def check_tokens():
    """Проверка наличия токенов."""
    missed_tokens = []
    tokens = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
              'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    # почему-то тест не проходит, если использую константу TOKENS.
    # Если внутри ф-ции словарь, то срабатывает. Подскажите, пжл, что можно сделать.
    for key, value in tokens.items():
        if not value:
            logger.critical(NO_TOKEN_MESSAGE.format(token=key))
            missed_tokens.append(key)
    if len(missed_tokens) > 0:
        raise ValueError(NO_TOKEN_MESSAGE.format(token=missed_tokens))


def send_message(bot, message):
    """Отправляем сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(TELEGRAM_MESSAGE_SENT.format(message=message))
        return True
    except telegram.TelegramError as telegram_error:
        logger.error(TELEGRAM_MESSAGE_NOT_SENT.format(
            message=message, telegram_error=telegram_error
        ), exc_info=True)
        return False


def get_api_answer(timestamp):
    """Получение данных с API YP."""
    parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response = requests.get(**parameters)
    except requests.exceptions.RequestException as request_error:
        raise ConnectionError(REQUEST_ERROR.format(
            request_error=request_error, parameters=parameters
        ))
    if response.status_code != 200:
        raise TheAnswerIsNot200Error(STATUS_CODE_200_ERROR.format(
            status_code=response.status_code, parameters=parameters
        ))
    response_json = response.json()
    for error in ('code', 'error'):
        if error in response_json:
            raise ResponseException(RESPONSE_ERROR.format(
                response_json=response_json[error],
                response_error=error,
                parameters=parameters
            ))
    return response_json


def check_response(response):
    """Проверяем данные в response."""
    if not isinstance(response, dict):
        raise TypeError(API_DICT_ERROR.format(data_type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(NO_KEY_ERROR.format(key='homeworks'))
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(API_LIST_ERROR.format(data_type=type(homeworks)))
    return homeworks


def parse_status(homeworks):
    """Анализируем статус если изменился."""
    status = homeworks.get('status')
    homework_name = homeworks.get('homework_name')
    if 'status' not in homeworks:
        raise ValueError(EMPTY_VALUE_ERROR.format(value=status))
    if 'homework_name' not in homeworks:
        raise ValueError(EMPTY_VALUE_ERROR.format(value=homework_name))
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_NOT_IN_HOMEWORK_VERDICTS.format(value=status))
    return CHANGE_HOMEWORK_STATUS.format(
        homework_name=homework_name, verdict=HOMEWORK_VERDICTS[status]
    )


def main():
    """Главная функция запуска бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                if send_message(bot, status):
                    timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message_error = MAIN_EXCEPTION_ERROR.format(error=error)
            logger.error(message_error, exc_info=True)
            if message_error != last_error_message:
                if send_message(bot, message_error):
                    last_error_message = message_error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(module)s - %(name)s - '
               '%(funcName)s: %(lineno)d - %(message)s',
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler(filename=__file__ + '.log', mode='w')]
    )
    main()
