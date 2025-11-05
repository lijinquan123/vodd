# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/16 11:01
# @Version     : Python 3.13.7
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
from prettytable import PrettyTable

from vodd.core.algorithms import format_duration, convert_to_num, check_video, check_dts
from vodd.core.constants import MediaName
from vodd.core.exceptions import *
from vodd.core.files import TEMP_DIR, ERROR_DIR
from vodd.core.models import Segment
from vodd.plugins import get_all_plugins
from vodd.plugins.__base_plugin__ import BasePlugin
from vodd.utils.request_adapter import get_request_kwargs

logger = logging.getLogger(__name__)


class Downloader(object):

    def __init__(self, save_path: str, rate: int = 5, **kwargs):
        if ffmpeg_path := shutil.which('ffmpeg'):
            self.ffmpeg_path = ffmpeg_path
        else:
            raise FFmpegNotFoundError('找不到FFmpeg程序,当前程序即刻停止')
        # 必须参数
        self.save_path = Path(save_path)
        self.threads_num = math.ceil(rate)
        self.kwargs = kwargs
        # 可选参数
        self.temp_dir = TEMP_DIR / md5(self.save_path.as_posix().encode('utf-8')).hexdigest()
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.per_timeout = kwargs['per_timeout']
        self.overall_timeout = kwargs['overall_timeout']
        self.max_download_times = kwargs['max_download_times']
        self.chunk_size = kwargs['chunk_size']
        self.max_segment_size = kwargs['max_segment_size']
        self.chunk_file_size = kwargs['chunk_file_size']
        self.segment_size = kwargs['segment_size']
        # 控制参数
        self.chunked_mode = False
        self.is_stop_all = False
        self.start_time = time.time()
        self.session = requests.Session()
        self.request_kwargs = get_request_kwargs(**kwargs)
        self.core = DownloadCore(self)
        self.tasks = []
        self.segments = defaultdict(lambda: defaultdict(list))
        self.inits = defaultdict(lambda: {})
        self.error = {}
        self.plugin: BasePlugin | None = None
        self.concat_paths = defaultdict(lambda: [])
        self.downloaded_size = defaultdict(lambda: [0, 0])

    def requester(self, method: str, url: str, **kwargs):
        code = None
        for i in range(self.max_download_times):
            try:
                if (resp := self.session.request(method, url, **{**self.request_kwargs, **kwargs})).ok:
                    break
                code = resp.status_code
            except requests.exceptions.SSLError:
                self.request_kwargs['verify'] = False
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                logger.warning('检测到存在SSL认证，已自动忽略')
                time.sleep(0.1)
            except (requests.exceptions.RequestException, Exception) as e:
                logger.error(f'第{i + 1}次请求异常: {e}')
                time.sleep(0.1)
        else:
            raise HTTPStatusCodeError(f'{code}')
        return resp

    @property
    def is_all_confirmed(self) -> bool:
        """
        是否所有的下载任务都已经确认
        :return:
        """
        for task in self.tasks:
            if task.confirmed is False:
                return False
        return True

    @staticmethod
    def remove(file: Path):
        try:
            if file.exists():
                file.unlink()
        except Exception as e:
            logger.error(f'文件删除错误: {file.name}, {e}')

    def concurrent(self):
        """
        并发下载任务
        :return:
        """
        with ThreadPoolExecutor(max_workers=self.threads_num) as executor:
            list(executor.map(self.download, self.tasks))

    def download_inits(self):
        for mt, keys in self.inits.items():
            for key, segment in keys.items():
                try:
                    if self.is_stop_all:
                        return
                    self.smart_save(segment.init_url, segment.headers, segment.init_path)
                except DownloadException as e:
                    self.is_stop_all = True
                    self.error = e.__dict__
                except Exception as e:
                    self.is_stop_all = True
                    logger.error(f'下载元数据异常: {mt}.{key[0]}, {e}')

    def download(self, task: Segment):
        try:
            if self.is_stop_all:
                return
            if (duration := time.time() - self.start_time) > self.overall_timeout:
                logger.warning(f'下载已超时：{int(duration)}, 终止程序运行')
                raise ReachMaxDownloadLimitError(f'timeout: {int(duration)}')
            self.smart_save(task.url, task.headers, task.filepath)
            task.confirmed = True
            self.plugin.decrypt(task).rename(task.filepath)
        except DownloadException as e:
            self.is_stop_all = True
            self.error = e.__dict__
        except Exception as e:
            self.is_stop_all = True
            logger.error(f'下载任务异常: {e}')

    def smart_save(self, url: str, headers: dict, path: Path, ):
        rk = {}
        if headers:
            rk['headers'] = headers
        self.downloaded_size.pop(path.name, None)
        if self.chunked_mode:
            st_time = time.time()
            with self.requester('get', url, stream=True, **rk) as resp, open(path, 'wb') as f:
                self.downloaded_size[path.name][1] = int(resp.headers.get('Content-Length', 0))
                for chunk in resp.iter_content(self.chunk_size):
                    f.write(chunk)
                    self.downloaded_size[path.name][0] += len(chunk)
                    if (
                            (duration := time.time() - self.start_time) > self.overall_timeout
                            or (duration := time.time() - st_time) > self.per_timeout
                    ):
                        self.downloaded_size.pop(path.name, None)
                        logger.warning(f'下载已超时：{int(duration)}, 终止程序运行')
                        raise ReachMaxDownloadLimitError(f'timeout: {int(duration)}')
        else:
            resp = self.requester('get', url, **rk)
            path.write_bytes(resp.content)
            self.downloaded_size[path.name] = [len(resp.content), len(resp.content)]

    def wipe(self):
        logger.info(f'删除缓存文件夹: {self.temp_dir}')
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def watchdog(self):
        while True:
            if self.is_stop_all or self.is_all_confirmed:
                sys.stdout.write("\n")
                break
            try:
                downloadeds = 0
                totals = 0
                for d, t in self.downloaded_size.values():
                    downloadeds += d
                    totals += t
                cost = int(time.time() - self.start_time)
                download_num = max(len(self.downloaded_size), 1)
                max_num = max(len(self.tasks), len(self.downloaded_size))
                predicted_cost = int(totals / (downloadeds or 1) * cost * max_num / download_num)
                # 耗时使用00:00, 文件大小使用MB, 速度使用MB/s
                sys.stdout.write(
                    f"\r{time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"耗时: {format_duration(cost)}, 预估总耗时: {format_duration(predicted_cost)}, 速度: {downloadeds / 1024 / 1024 / cost:.2f}MB/s, "
                    f"{downloadeds / (totals or 1) * 100:6.2f}%({round(downloadeds / 1024 / 1024, 1)}MB/{round(totals / 1024 / 1024, 1)}MB), "
                    f"{download_num / max_num * 100:6.2f}%({download_num}/{max_num})"
                )
                sys.stdout.flush()
            except Exception as e:
                logger.exception(e)
            time.sleep(1)

    def start(self):
        """
        开启下载程序

        下载前删除已存在的临时文件夹
        所有任务下载成功后则合并临时文件夹到指定路径
        删除临时文件夹
        :return:
        """
        self.wipe()
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self.plugin = self.core.get_suitable_plugin()
            logger.info(f'使用插件：{self.plugin.__class__.__name__}')
            formats = self.core.select()
            segments = self.plugin.get_segments(formats)
            if self.segment_size:
                segments = segments[:self.segment_size]
            self.tasks = segments
            self.core.add_segments_path()
            logger.info(f'总任务数：{len(self.tasks)}')
            self.core.classify()
            self.core.check_video(self.core.pre_download(self.tasks[0]))
            self.download_inits()
            threading.Thread(target=self.watchdog).start()
            self.concurrent()
            time.sleep(1)
            if self.is_all_confirmed:
                self.core.concat()
                self.core.merge()
            else:
                raise DownloadTaskError('未全部下载完成')
            if self.save_path.exists():
                self.core.check_video(self.save_path, full=True)
                check_dts(self.save_path)
        except DownloadException as e:
            logger.error(f'下载异常: {e}')
            if not self.error:
                self.error = e.__dict__
        except Exception as e:
            logger.exception(f'下载异常, 终止程序运行: {e}')
            if not self.error:
                self.error = {'message': 'Exception', 'reason': str(e)}
        self.wipe()
        if self.error and self.save_path.exists():
            error_file = ERROR_DIR / self.save_path.name
            logger.error(f'将文件移动到错误文件夹: {error_file.as_posix()}')
            shutil.move(self.save_path.as_posix(), error_file.as_posix())
        return {
            'error': self.error,
            'save_path': self.save_path.as_posix(),
        }


class DownloadCore(object):

    def __init__(self, downloader: Downloader):
        self.downloader = downloader

    def get_suitable_plugin(self) -> BasePlugin:
        if not (name := self.downloader.kwargs.get('plugin', '').lower()):
            resp = self.downloader.requester('head', self.downloader.kwargs['url'])
            suffix = Path(urlparse(resp.url).path).suffix.lower()
            if (
                    "mpegurl" in (ctype := resp.headers.get("Content-Type", "").lower())
                    or "m3u8" in ctype
                    or ".m3u8" == suffix
            ):
                name = "hls"
            elif (
                    "dash+xml" in ctype
                    or "mpd" in ctype
                    or ".mpd" == suffix
            ):
                name = "dash"
            elif ctype.startswith("video/") or "octet-stream" in ctype:
                # 对于视频类型、二进制流，默认认为可直接下载
                name = "stream"
            else:
                raise NotFoundError(f'没有找到合适的插件: {ctype}')
        if name not in (plugins := get_all_plugins()):
            raise UnsupportedError(f'没有找到插件: {name}')
        return plugins[name](downloader=self.downloader)

    def check_video(self, filepath: Path, full: bool = False):
        command = f'ffprobe -v error -select_streams v:0 -show_entries "stream=index,codec_type,width,height,codec_name,r_frame_rate,bit_rate,duration:format=bit_rate" -of json "{filepath.as_posix()}"'
        try:
            meta = json.loads(os.popen(command).read().strip())
            if not (streams := meta['streams']):
                streams = meta['programs'][0]['streams']
            stream_info = streams[0]
        except KeyError, Exception:
            raise CheckVideoError(f'无法探测媒体信息，视频内容错误')
        logger.info(f'探测到视频格式: {json.dumps(meta, ensure_ascii=False)}')
        # 通过探测结果再次筛选视频
        video = {
            "v_height": stream_info['height'] or 0,
        }
        if full:
            video['v_framerate'] = convert_to_num(stream_info['r_frame_rate']) or 0
            video['v_bandwidth'] = convert_to_num(meta['format']['bit_rate'])
        check_video(**video, **self.downloader.kwargs)

    def pre_download(self, segment: Segment) -> Path:
        if segment.init_url:
            url = segment.init_url
            filepath = segment.init_path
        else:
            url = segment.url
            filepath = segment.filepath
        self.downloader.smart_save(url, segment.headers, filepath)
        if not segment.init_url:
            self.downloader.plugin.decrypt(segment).rename(segment.filepath)
        resp = self.downloader.requester('head', segment.url)
        if (
                resp.headers.get('Accept-Ranges', '').lower() == 'bytes'
                and 'Content-Length' in resp.headers
                and int(resp.headers['Content-Length']) > self.downloader.max_segment_size
        ):
            self.downloader.chunked_mode = True
        return filepath

    def classify(self):
        self.downloader.tasks.sort(key=lambda x: (MediaName.index(x.type), x.group_no, x.index))
        for segment in self.downloader.tasks:
            self.downloader.segments[segment.type][segment.group_no].append(segment)
            if not segment.init_url:
                continue
            key = segment.group_no, Path(urlparse(segment.init_url).path).name
            self.downloader.inits[segment.type][key] = segment

        nums = defaultdict(lambda: 0)
        for mt, keys in self.downloader.inits.items():
            for (group_no, *_), segment in keys.items():
                nums[mt, group_no] += 1
        for key, v in nums.items():
            if v > 1:
                raise UnsupportedError(f'轨道不支持多个初始化文件, {key}: {v}')

    def add_segments_path(self):
        for segment in self.downloader.tasks:
            suffix = Path(urlparse(segment.url).path).suffix
            segment.filepath = self.downloader.temp_dir / f'{segment.type}_{segment.group_no:05}_{segment.index:010}{suffix}'
            if segment.init_url:
                name = Path(urlparse(segment.init_url).path).name
                segment.init_path = self.downloader.temp_dir / f'{segment.type}_{segment.group_no:05}_{name}'

    def concat(self):
        """拼接同一轨道的切片"""
        for mt, groups in self.downloader.segments.items():
            for group_no, segments in groups.items():
                gpath = self.downloader.temp_dir / f'group_{mt}_{(fs := segments[0]).group_no}{Path(fs.filepath).suffix}'
                self.downloader.remove(gpath)
                self.downloader.concat_paths[mt].append(gpath)
                if fs.init_path:
                    fs.init_path.rename(gpath)
                with open(gpath, 'ab') as fa:
                    for segment in segments:
                        with open(segment.filepath, 'rb') as fr:
                            while chunk := fr.read(self.downloader.chunk_size):
                                fa.write(chunk)
                        self.downloader.remove(segment.filepath)

    def merge(self):
        """合并切片"""
        self.downloader.remove(self.downloader.save_path)
        video_path = self.downloader.concat_paths[MediaName.video][0]
        if MediaName.audio in self.downloader.concat_paths:
            merged_path = self.downloader.temp_dir / f'merged_{video_path.name}'
            command = f'{self.downloader.ffmpeg_path} -nostats -y'
            _is = f' -i "{video_path.as_posix()}"'
            _maps = ' -c copy -map 0:v? -map 0:a?'
            for i, audio in enumerate(self.downloader.concat_paths.get(MediaName.audio, []), start=1):
                _is += f' -i "{audio.as_posix()}"'
                _maps += f' -map {i}:a'
            command += _is
            command += _maps
            # 需要添加字幕的话，要合并成MKV
            command += f' -f mpegts "{merged_path.as_posix()}"'
            result = subprocess.run(
                command,
                shell=True,  # 允许使用字符串形式的命令
                capture_output=True,  # 捕获 stdout 和 stderr
                text=True  # 输出自动解码为字符串
            )
            if result.returncode != 0:
                raise MediaMergeError(f'{result.returncode}, {result.stderr}')
        else:
            merged_path = video_path
        shutil.move(merged_path.as_posix(), self.downloader.save_path.as_posix())

    def select(self):
        available_formats = self.downloader.plugin.get_formats()
        table = PrettyTable()
        table.field_names = ["序号", "分辨率/语言", "码率/描述", "帧率/采样率", "编码", "MIME类型"]
        for mt, fs in available_formats.items():
            for f in fs:
                if mt == MediaName.video:
                    row = [f.index, f.resolution, f.bandwidth, f.framerate, f.codecs, f.mime_type]
                else:
                    row = [f.index, f.language, f.label, f.audio_sampling_rate, f.codecs, f.mime_type]
                table.add_row(row)
        logger.info(f'可选择的格式有：\n{table}')

        formats = self.downloader.plugin.select_formats(available_formats)
        shows = {}
        for mt, fs in formats.items():
            shows[mt] = ','.join([str(f.index) for f in fs])
        logger.info(f'已选择格式：{'; '.join([f'{mt}:{shows[mt]}' for mt in shows])}')
        return formats
