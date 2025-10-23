# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 16:35
# @Version     : Python 3.14.0
import copy
import itertools
from pathlib import Path
from typing import List

from vodd.core.algorithms import get_resolution
from vodd.core.constants import MediaName
from vodd.core.models import VideoMedia, Segment
from vodd.plugins import BasePlugin


class Stream(BasePlugin):

    def get_formats(self) -> dict:
        return {
            MediaName.video: [
                VideoMedia(
                    index=0,
                    data=self.downloader.kwargs['url'],
                    height=0,
                    resolution=get_resolution(0, 0),
                    bandwidth=0,
                    framerate=0,
                    codecs='',
                    mime_type=MediaName.video,
                )
            ]
        }

    def get_segments(self, formats: dict) -> List[Segment]:
        resp = self.downloader.requester('head', self.downloader.kwargs['url'])
        if not (
                resp.headers.get('Accept-Ranges', '').lower() == 'bytes'
                and 'Content-Length' in resp.headers
        ):
            return [
                Segment(
                    type=MediaName.video,
                    group_no=0,
                    index=0,
                    url=self.downloader.kwargs['url'],
                )
            ]
        content_length = int(resp.headers['Content-Length'])
        headers = copy.deepcopy(self.downloader.request_kwargs['headers'])
        headers['range'] = (f"bytes=0"
                            f"-{min(self.downloader.max_segment_size, content_length) - 1}")
        segments = [
            Segment(
                type=MediaName.video,
                group_no=0,
                index=0,
                url=self.downloader.kwargs['url'],
                headers=headers,
            )
        ]
        for index, start_position in enumerate(
                itertools.count(self.downloader.max_segment_size, self.downloader.chunk_file_size), start=1):
            if start_position >= content_length:
                break
            headers = copy.deepcopy(self.downloader.request_kwargs['headers'])
            headers['range'] = (f"bytes={start_position}"
                                f"-{min(start_position + self.downloader.chunk_file_size, content_length) - 1}")
            segments.append(Segment(
                type=MediaName.video,
                group_no=0,
                index=index,
                url=self.downloader.kwargs['url'],
                headers=headers,
            ))
        return segments

    def decrypt(self, segment: Segment) -> Path:
        return segment.filepath
