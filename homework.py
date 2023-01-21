import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
import telegram

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
TG_MSG_SENT = 'Сообщение в Telegram отправлено: {message}'
TG_MSG_NOT_SENT = ('Сообщение в Telegram не отправлено: {message},'
                   '{telegram_error}')
REQUEST_ERROR = 'Код ответа API (RequestException): {request_error}'
STATUS_CODE_200_ERROR = 'Код ответа API равен {status_code}, а не 200'
API_DICT_ERROR = 'Ожидаемый тип данных - словарь, получен {data_type}'
API_LIST_ERROR = 'Ожидаемый тип данных - список, получен {data_type}'
EMPTY_KEY_ERROR = 'Отсутствует ключ {key}.'
EMPTY_VALUE_ERROR = 'Отсутствует значение {value}'
STATUS_NOT_IN_HOMEWORK_VERDICTS = 'Недокументированный статус {value}'
CHANGE_HOMEWORK_STATUS = ('Изменился статус проверки работы'
                          '{homework_name}. {verdict}')
MAIN_EXCEPTION_ERROR = 'Сбой в работе программы: {error}'
RESPONSE_ERROR = 'В ключе ответа {response_json} есть ошибка {response_error}'
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
    tokens_bool = True
    for token in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if token is None:
            tokens_bool = False
            logger.critical(NO_TOKEN_MESSAGE.format(token=token))
    return tokens_bool


def send_message(bot, message):
    """Отправляем сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(TG_MSG_SENT.format(message=message))
    except telegram.TelegramError as telegram_error:
        logger.error(TG_MSG_NOT_SENT.format(
            message=message, telegram_error=telegram_error
        ), exc_info=True)


def get_api_answer(timestamp):
    """Получение данных с API YP."""
    kwargs = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response = requests.get(**kwargs)
    except requests.exceptions.RequestException as request_error:
        raise RequestExceptionError(REQUEST_ERROR.format(
            request_error=request_error, **kwargs
        ))
    if response.status_code != 200:
        raise TheAnswerIsNot200Error(STATUS_CODE_200_ERROR.format(
            status_code=response.status_code, **kwargs
        ))
    response_json = response.json()
    for error in ('code', 'error'):
        if error in response_json:
            raise ResponseException(RESPONSE_ERROR.format(
                response_json=response_json[error],
                response_error=error,
                **kwargs
            ))
    return response_json


def check_response(response):
    """Проверяем данные в response."""
    if not isinstance(response, dict):
        raise TypeError(API_DICT_ERROR.format(data_type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(EMPTY_KEY_ERROR.format(key='homeworks'))
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(API_LIST_ERROR.format(data_type=type(homeworks)))
    if homeworks == []:
        return {}
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
    # # return CHANGE_HOMEWORK_STATUS.format(
    # #     homework_name=homework_name, verdict=HOMEWORK_VERDICTS[status]
    # )
    # С кодом выше тест не проходит.
    return (f'Изменился статус проверки работы "{homework_name}".'
            f'{HOMEWORK_VERDICTS[status]}')


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        logger.critical(NO_TOKEN_MESSAGE)
        raise SystemExit(NO_TOKEN_MESSAGE)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_msg = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message_error = MAIN_EXCEPTION_ERROR.format(error=error)
            if error_msg != message_error:
                error_msg = message_error
                send_message(bot, message_error)
                logger.error(message_error, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s',
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler(filename=__file__ + '.log', mode='w')]
    )
    main()
