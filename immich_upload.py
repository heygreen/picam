#!/usr/bin/python3

import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL')


def upload(file):
    stats = os.stat(file)

    headers = {
        'Accept': 'application/json',
        'x-api-key': API_KEY
    }

    data = {
        'deviceAssetId': f'{file}-{stats.st_mtime}',
        'deviceId': 'python',
        'fileCreatedAt': datetime.fromtimestamp(stats.st_mtime),
        'fileModifiedAt': datetime.fromtimestamp(stats.st_mtime),
        'isFavorite': 'false',
    }

    files = {
        'assetData': open(file, 'rb')
    }

    response = requests.post(
        f'{BASE_URL}/assets', headers=headers, data=data, files=files)

    print(response.json())
    # {'id': 'ef96f635-61c7-4639-9e60-61a11c4bbfba', 'duplicate': False}