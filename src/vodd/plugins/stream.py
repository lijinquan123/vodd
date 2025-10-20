# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 16:35
# @Version     : Python 3.14.0
from pathlib import Path

from vodd.plugins import BasePlugin


class Stream(BasePlugin):

    def media_decrypt(self, path: Path) -> Path:
        """解密媒体文件"""
        return path
