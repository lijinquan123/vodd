# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/7/18 17:47
# @Version     : Python 3.6.8
from typing import List
from urllib.parse import urlparse

import m3u8

from vodd.core.exceptions import *
from vodd.core.models import VideoMedia


def parse_m3u8(content: str, url: str = None) -> m3u8.M3U8:
    media = m3u8.loads(content)
    if url is not None:
        media.base_uri = url.replace(urlparse(url).query, '').strip('?').rsplit('/', 1)[0] + '/'
    return media


def format_duration(seconds: float) -> str:
    minutes, sec = divmod(seconds, 60)
    return f"{int(minutes)}m{int(sec)}s"


def convert_to_num(s: str) -> float:
    if not s:
        return 0
    if isinstance(s, str) and '/' in s:
        a, b = s.split('/', 1)
        return float(a) / float(b)
    return float(s)


def get_resolution(width: int = None, height: int = None) -> str:
    resolution = []
    if width:
        resolution.append(str(width))
    if height:
        resolution.append(str(height))
    return 'x'.join(resolution)


def best_video(medias: List[VideoMedia], **kwargs) -> VideoMedia:
    # best, min, max
    defaults = {
        'height': (1080, 480, 1080),
        'bandwidth': (3 * 1024 * 1024, 1024, 10 * 1024 * 1024),
        'framerate': (25, 0, 120),
    }
    rules = {}
    for key in defaults:
        rules[key] = kwargs.get(key, defaults[key])
    allowed_medias = [
        media for media in medias
        if all(not media[k] or v[1] <= media[k] <= v[2] for k, v in rules.items())
    ]
    if not allowed_medias:
        raise UnsupportedError(f'没有符合要求的视频：{', '.join([f'{k}={v[0]}' for k, v in rules.items()])}')
    media = allowed_medias[0]
    for key in rules:
        if media[key]:
            return sorted(allowed_medias, key=lambda x: abs(x[key] - rules[key][0]))[0]
    return media
