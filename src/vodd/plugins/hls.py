# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 16:39
# @Version     : Python 3.14.0
import logging
import struct
from pathlib import Path
from typing import List

import m3u8
from Crypto.Cipher import AES

from vodd.core.algorithms import parse_m3u8, get_resolution, convert_to_num
from vodd.core.constants import MediaName
from vodd.core.exceptions import NotFoundError
from vodd.core.models import VideoMedia, AudioMedia, Segment, Cipher
from vodd.plugins import BasePlugin

logger = logging.getLogger(__name__)


class HLS(BasePlugin):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = {}

    def get_formats(self) -> dict:
        resp = self.downloader.requester('GET', self.downloader.kwargs['url'])
        media = parse_m3u8(resp.text, resp.url)

        videos = []
        for index, playlist in enumerate(media.playlists):  # type: int, m3u8.Playlist
            width = height = 0
            if resolution := (stream_info := playlist.stream_info).resolution:
                width, height = resolution
            videos.append(VideoMedia(
                index=index,
                data=playlist.absolute_uri,
                height=height or 0,
                resolution=get_resolution(width, height),
                bandwidth=stream_info.average_bandwidth or stream_info.bandwidth or 0,
                framerate=convert_to_num(stream_info.frame_rate) or 0,
                codecs=stream_info.codecs or '',
                mime_type=MediaName.video,
            ))
        if not videos:
            videos.append(VideoMedia(
                index=0,
                data=resp.url,
                height=0,
                resolution=get_resolution(0, 0),
                bandwidth=0,
                framerate=0,
                codecs='',
                mime_type=MediaName.video,
            ))

        audios = []
        for index, audio in enumerate(media.media, start=len(videos)):  # type: int, m3u8.Media
            if audio.type != 'AUDIO':
                continue
            audios.append(AudioMedia(
                index=index,
                data=audio.absolute_uri,
                id=audio.group_id,
                language=audio.language or '',
                label=audio.name or '',
                codecs=audio.channels or '',
                audio_sampling_rate='',
                mime_type=MediaName.audio,
            ))
        formats = {
            MediaName.video: videos,
        }
        if audios:
            formats[MediaName.audio] = audios
        return formats

    def get_single_media_segments(self, url: str, group_no: int, media_type: str):
        resp = self.downloader.requester('GET', url)
        media = parse_m3u8(resp.text, resp.url)
        segments = []
        for index, segment in enumerate(media.segments, start=1):
            init_url = None
            if segment.init_section:
                init_url = segment.init_section.absolute_uri
            cipher = Cipher(name='')
            if (key := segment.key) and key.absolute_uri:
                if (iv := key.iv) is not None:
                    if iv[:2] == '0x':
                        iv = iv[2:]
                    iv = bytes.fromhex(iv)
                cipher = Cipher(
                    name=key.method,
                    params={"url": key.absolute_uri, "iv": iv},
                )
            segments.append(Segment(
                type=media_type,
                group_no=group_no,
                index=index,
                cipher=cipher,
                url=segment.absolute_uri,
                duration=segment.duration,
                init_url=init_url or '',
            ))
        return segments

    def get_segments(self, formats: dict) -> List[Segment]:
        segments = self.get_single_media_segments(formats[MediaName.video][0].data, 0, MediaName.video)
        for group_no, fmt in enumerate(formats.get(MediaName.audio) or []):
            segments.extend(self.get_single_media_segments(fmt.data, group_no, MediaName.audio))
        return segments

    def decrypt(self, segment: Segment) -> Path:
        if segment.cipher.name:
            if 'url' in segment.cipher.params:
                if (url := segment.cipher.params['url']) in self.keys:
                    key = self.keys[url]
                else:
                    with self._lock:
                        if url not in self.keys:
                            resp = self.downloader.requester('GET', url)
                            if key := resp.content:
                                self.keys[url] = key
                                logger.warning(f'添加加密key: {url=}, {key=}')
                            else:
                                raise NotFoundError(f'获取key失败: {key=}')
            elif 'key' in segment.cipher.params:
                key = segment.cipher.params['key']
            # 64字节key
            if len(key) == 64:
                if key not in self.keys:
                    k = bytes([
                        54, 67, 48, 54, 48, 52, 56, 52, 69, 50, 57, 50, 52, 50, 54, 65,
                        51, 49, 55, 54, 56, 68, 70, 57, 65, 55, 67, 54, 70, 66, 56, 49
                    ])
                    nk = bytes.fromhex(AES.new(k, AES.MODE_CBC, key[:16]).decrypt(key[16:])[:32].decode('utf-8'))
                    self.keys[key] = nk
            else:
                self.keys[key] = key
            iv = segment.cipher.params.get('iv') or struct.pack(">8xq", int(float(segment.index)))
            segment.filepath.write_bytes(
                AES.new(self.keys[key], AES.MODE_CBC, iv=iv).decrypt(segment.filepath.read_bytes())
            )
        # TS额外处理
        if segment.filepath.suffix.lower() == '.ts':
            symbol = b'G@'
            if (content := segment.filepath.read_bytes())[:2] != symbol and (position := content.find(symbol)) > -1:
                segment.filepath.write_bytes(content[position:])
        return segment.filepath
