# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/7/18 17:47
# @Version     : Python 3.6.8
import subprocess
from pathlib import Path
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


def get_rules(**kwargs):
    # best, min, max
    defaults = {
        'height': (1080, 480, 1080),
        'bandwidth': (3 * 1024 * 1024, 1024, 10 * 1024 * 1024),
        'framerate': (25, 0, 240),
    }
    rules = {}
    for key in defaults:
        rules[key] = kwargs.get(key, defaults[key])
    return rules


def best_video(medias: List[VideoMedia], **kwargs) -> VideoMedia:
    rules = get_rules(**kwargs)
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


def check_video(v_height: int, v_bandwidth: float = 0, v_framerate: float = 0, **kwargs):
    rules = get_rules(**kwargs)
    _, min_height, max_height = rules['height']
    if v_height > max_height:
        raise ResolutionTooHighError(f'{v_height} > {max_height}')
    if v_height < min_height:
        raise ResolutionTooLowError(f'{v_height} < {max_height}')
    if v_bandwidth:
        _, min_bandwidth, max_bandwidth = rules['bandwidth']
        if v_bandwidth > max_bandwidth:
            raise BandwidthTooHighError(f'{v_bandwidth} > {max_bandwidth}')
        if v_bandwidth < min_bandwidth:
            raise BandwidthTooLowError(f'{v_bandwidth} < {min_bandwidth}')
    if v_framerate:
        _, min_framerate, max_framerate = rules['framerate']
        if v_framerate > max_framerate:
            raise FramerateTooHighError(f'{v_framerate} > {max_framerate}')
        if v_framerate < min_framerate:
            raise FramerateTooLowError(f'{v_framerate} < {min_framerate}')


def check_dts(filepath: Path):
    command = f'ffprobe -v error -select_streams v:0 -show_entries packet=pts,pts_time,dts,dts_time,duration_time -of csv=p=0 "{filepath.as_posix()}"'
    if (p := subprocess.run(
            command,
            shell=True,  # 允许使用字符串形式的命令
            capture_output=True,  # 捕获 stdout 和 stderr
            text=True  # 输出自动解码为字符串
    )).returncode != 0:
        raise DTSCheckError(f'{p.returncode}, {p.stderr}')
    problems = []
    duration = 0
    prev_dts = 0
    for frame in p.stdout.strip().split('\n'):
        pts, pts_time, dts, dts_time, duration_time = frame.strip(',').split(',')
        try:
            dts = float(dts)
        except ValueError, Exception:
            dts = prev_dts
        try:
            duration_time = float(duration_time)
        except ValueError, Exception:
            duration_time = 0
        if prev_dts - dts >= 2 * duration_time or duration_time == 0:
            problems.append(format_duration(duration))
        prev_dts = dts
        duration += duration_time
    if problems:
        raise DTSCheckError(",".join(problems))
