# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/16 12:09
# @Version     : Python 3.14.0
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Cipher(BaseModel):
    name: str
    params: dict = {}


class Segment(BaseModel):
    type: str
    group_no: int
    index: int
    url: str
    headers: dict = {}
    filepath: Path = None
    duration: float = None
    discontinuity: bool = False
    # 加密参数
    cipher: Cipher = Cipher(name='')
    # 元数据链接
    init_url: str = None
    # 元数据路径
    init_path: Path = None
    confirmed: bool = False


class VideoMedia(BaseModel):
    index: int
    data: Any = ''
    height: int = 0
    resolution: str = ''
    bandwidth: int = 0
    framerate: float = 0
    codecs: str = ''
    mime_type: str = ''

    def __getitem__(self, item):
        return getattr(self, item)


class AudioMedia(BaseModel):
    index: int
    data: Any = ''
    id: str = ''
    language: str = ''
    label: str = ''
    audio_sampling_rate: str = ''
    codecs: str = ''
    mime_type: str = ''

    def __getitem__(self, item):
        return getattr(self, item)
