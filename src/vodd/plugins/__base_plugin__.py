# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/28 16:45
# @Version     : Python 3.13.7
import abc
import threading
from pathlib import Path
from typing import List

from vodd.core.algorithms import best_video
from vodd.core.constants import MediaName
from vodd.core.models import Segment


class BasePlugin(metaclass=abc.ABCMeta):
    usable = True

    def __init__(self, downloader):
        from vodd.downloader import Downloader
        self.downloader: Downloader = downloader
        self.has_ad = False
        self._lock = threading.RLock()

    @abc.abstractmethod
    def get_formats(self) -> dict:
        """获取格式"""

    def select_formats(self, formats: dict) -> dict:
        """选择格式"""
        video = best_video(formats[MediaName.video], **self.downloader.kwargs)
        formats[MediaName.video] = [video]
        return formats

    @abc.abstractmethod
    def get_segments(self, formats: dict) -> List[Segment]:
        """获取切片"""

    @abc.abstractmethod
    def decrypt(self, segment: Segment) -> Path:
        """解密切片"""
