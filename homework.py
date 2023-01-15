from dotenv import load_dotenv
import datetime
import json
import logging
import os
import requests
import telegram
import time

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


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


class EmptyStatusError(Exception):
    """Пустой статус."""


def check_tokens():
    """Проверка наличия токенов."""
    no_tokens_msg = (
        'Программа принудительно остановлена. '
        'Отсутствует обязательная переменная окружения:')
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} PRACTICUM_TOKEN')
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} TELEGRAM_TOKEN')
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logger.critical(
            f'{no_tokens_msg} TELEGRAM_CHAT_ID')
    return tokens_bool


def send_message(bot, message):
    """Отправляем сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Получение данных с API YP."""
    timestamp = timestamp or int(time.time())
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=headers, params=payload)
        if response.status_code != 200:
            code_api_msg = (
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}')
            logger.error(code_api_msg)
            raise TheAnswerIsNot200Error(code_api_msg)
        return response.json()
    except requests.exceptions.RequestException as request_error:
        code_api_msg = f'Код ответа API (RequestException): {request_error}'
        logger.error(code_api_msg)
        raise RequestExceptionError(code_api_msg) from request_error
    except json.JSONDecodeError as value_error:
        code_api_msg = f'Код ответа API (ValueError): {value_error}'
        logger.error(code_api_msg)
        raise json.JSONDecodeError(code_api_msg) from value_error


def check_response(response):
    """Проверяем данные в response."""
    if not isinstance(response, dict):
        code_api_msg = (
            'Ошибка ожидаемый тип данных - словарь')
        logger.error(code_api_msg)
        raise TypeError(code_api_msg)
    if response.get('homeworks') is None:
        code_api_msg = (
            'Ошибка ключа homeworks или response'
            'имеет неправильное значение.')
        logger.error(code_api_msg)
        raise EmptyDictionaryOrListError(code_api_msg)
    if not isinstance(response['homeworks'], list):
        code_api_msg = (
            'Ошибка ожидаемый тип данных - словарь')
        logger.error(code_api_msg)
        raise TypeError(code_api_msg)
    if response['homeworks'] == []:
        return {}
    return response['homeworks'][0]


def parse_status(homework):
    """Анализируем статус если изменился."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status is None:
        code_api_msg = f'Ошибка пустое значение status: {status}'
        logger.error(code_api_msg)
        raise EmptyStatusError(code_api_msg)
    if homework_name is None:
        code_api_msg = f'Ошибка пустое значение homework_name: {homework_name}'
        logger.error(code_api_msg)
        raise EmptyStatusError(code_api_msg)
    if status not in HOMEWORK_VERDICTS:
        code_api_msg = f'Ошибка недокументированный статус: {status}'
        logger.error(code_api_msg)
        raise UndocumentedStatusError(code_api_msg)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Главная функция запуска бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, f'Я начал свою работу:'
                 f'{datetime.datetime.now().strftime("%d-%m-%Y %H:%M")}')
    timestamp = int(time.time())
    status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_day', timestamp)
            homework = check_response(response)
            if homework and homework['status'] != status:
                send_message(bot, parse_status(homework))
                status = homework['status']
            else:
                logger.info('Изменений нет, ждем 10 минут и проверяем API')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.critical(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
