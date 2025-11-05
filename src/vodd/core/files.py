# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 11:47
# @Version     : Python 3.14.0
from pathlib import Path

TEMP_DIR = Path('/home/www/tmp/vodd/')
ERROR_DIR = Path('/home/www/tmp/vodd/error')
ERROR_DIR.mkdir(parents=True, exist_ok=True)
