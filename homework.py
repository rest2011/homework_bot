import logging
import os
import requests
import time

from dotenv import load_dotenv 
from telegram import Bot
from telegram.ext import Updater

load_dotenv()

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {os.getenv("PRACTIKUM_TOKEN")}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

bot = Bot(token=os.getenv('TELEGRAM_TOKEN'))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

def check_tokens():
    while True:
        try:
            os.getenv('TELEGRAM_TOKEN') != None
            os.getenv('PRACTIKUM_TOKEN') != None
            os.getenv('TELEGRAM_CHAT_ID') != None
        except Exception as error:
            logging.critical(f'Сбой в работе программы: {error}')

def send_message(bot, message):
    ...


def get_api_answer(timestamp):
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    if homework_statuses.status_code == 200:
        homework_statuses.json()

def check_response(response):
    ...


def parse_status(homework):
    ...

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    ...

    bot = telegram.Bot(token=os.getenv('TELEGRAM_TOKEN'))
    timestamp = int(time.time())

    ...

    while True:
        try:

            ...

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            ...
        ...


if __name__ == '__main__':
    main()
