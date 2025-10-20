# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/28 18:39
# @Version     : Python 3.13.7
import base64
import copy
import logging
import threading
from pathlib import Path
from typing import List

from DRM import mp4parse, decrypter
from DRM.widevine.cdm import ContentDecryptionModules
from DRM.widevine.oemcrypto import OEMCrypto

from vodd.core.algorithms import convert_to_num, best_video, get_resolution
from vodd.core.constants import SUPPORTED_DRM_CIPHERS, MediaName
from vodd.core.exceptions import *
from vodd.core.models import Segment, VideoMedia, AudioMedia
from vodd.format_parser.dash.parser import Parser
from vodd.plugins.__base_plugin__ import BasePlugin
from vodd.utils.dash_helper import get_representations, get_video_segments, get_audios_segments
from vodd.utils.request_adapter import get_request_kwargs

logger = logging.getLogger(__name__)


class DASH(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drm_key_content = ''
        self._drm_lock = threading.RLock()

    def pre_checker(self, segment: Segment):
        if segment.cipher.name:
            if segment.cipher.name not in SUPPORTED_DRM_CIPHERS:
                raise UnsupportedError(f'暂不支持DRM: {segment.cipher.name}')
            if not (pkp := self.downloader.kwargs['private_key_path']) or not Path(pkp).exists():
                raise NotFoundError(f'未找到DRM私钥: {pkp}')
            if not (cip := self.downloader.kwargs['client_id_path']) or not Path(cip).exists():
                raise NotFoundError(f'未找到DRM客户端ID: {cip}')
            if not self.downloader.kwargs['drm_request']:
                raise NotFoundError('未提供DRM请求数据')
            logger.warning(f'检测到DRM版权格式：{segment.cipher.name}')

    def get_license(self, request: dict) -> bytes:
        if 'method' not in (kwargs := get_request_kwargs(**request, with_url=True)):
            kwargs['method'] = 'POST'
        if func_code := request.get('function'):
            kwargs['data'] = eval(func_code.strip())(request['data'])
        resp = self.downloader.requester(**kwargs)
        return resp.content

    def decrypt(self, segment: Segment) -> Path:
        if segment.cipher.name:
            if segment.cipher.name not in SUPPORTED_DRM_CIPHERS:
                raise UnsupportedError(f'暂不支持DRM: {segment.cipher.name}')
            encrypt_file = segment.filepath
            try:
                if not self.drm_key_content:
                    with self._drm_lock:
                        # 双重检查，防止重复进入
                        if not self.drm_key_content:
                            logger.warning(f'正在请求DRM密钥')
                            # pssh一般只在元数据中
                            pssh_file = segment.init_path if segment.init_path else encrypt_file
                            dmp = mp4parse.mp4dump(pssh_file.as_posix())
                            pssh = mp4parse.get_pssh(dmp, pssh_file.as_posix())
                            if not pssh:
                                return encrypt_file
                            kid = mp4parse.get_kids(dmp)[0]
                            # 通过请求许可链接获取许可数据
                            cdm = ContentDecryptionModules(base64.b64decode(pssh))
                            private_key = Path(self.downloader.kwargs['private_key_path']).read_bytes()
                            raw_client_id = Path(self.downloader.kwargs['client_id_path']).read_bytes()
                            license_request = cdm.get_license_request(private_key, raw_client_id)
                            drm_request = copy.deepcopy(self.downloader.kwargs['drm_request'])
                            drm_request['data'] = license_request.raw
                            license_data = self.get_license(drm_request)
                            oem = OEMCrypto(license_data, license_request.msg, private_key)
                            # 返回解密秘钥
                            self.drm_key_content = f'{kid}:{oem.decrypt().todict()[kid]}'
                            logger.warning(f'DRM [kid:key]: {self.drm_key_content}')
                # DRM 解密
                decrypt_file = encrypt_file.with_stem(f'{encrypt_file.stem}_drm_decrypt')
                decrypter.decrypting_file(
                    encrypt_file.as_posix(), decrypt_file.as_posix(), self.drm_key_content, segment.init_path.as_posix()
                )
                if not decrypter.has_decrypted(encrypt_file.as_posix(), decrypt_file.as_posix()):
                    self.downloader.remove(decrypt_file)
                    raise DRMDecryptionError(f"{self.drm_key_content=}")
                return decrypt_file
            finally:
                self.downloader.remove(encrypt_file)
        elif segment.init_path:
            segment.filepath.write_bytes(segment.init_path.read_bytes() + segment.filepath.read_bytes())
        return segment.filepath

    def get_segments(self, formats: dict) -> List[Segment]:
        segments = get_video_segments(formats[MediaName.video][0].data)
        self.pre_checker(segments[0])
        for ass in get_audios_segments([f.data for f in formats[MediaName.audio]]):
            segments.extend(ass)
        return segments

    def get_formats(self) -> dict:
        resp = self.downloader.requester('GET', self.downloader.kwargs['url'])
        mpd = Parser.from_string(resp.text, resp.url)
        if (c := len(mpd.periods)) > 1:
            raise UnsupportedError(f'暂不支持多个Period: {c}')
        representations = get_representations(mpd.periods[0].adaptation_sets)
        if MediaName.video not in representations:
            raise NotFoundError(f'未找到视频：{list(representations)}')

        # 获取视频
        videos = []
        for index, video in enumerate(representations[MediaName.video]):
            videos.append(VideoMedia(
                index=index,
                data=video,
                height=video.height or 0,
                resolution=get_resolution(video.width, video.height),
                bandwidth=video.bandwidth or 0,
                framerate=convert_to_num(video.frame_rate) or 0,
                codecs=video.codecs or '',
                mime_type=video.mime_type or '',
            ))

        # 获取音频
        audios = []
        for index, audio in enumerate(representations[MediaName.audio], start=len(videos)):
            audios.append(AudioMedia(
                index=index,
                data=audio,
                id=audio.id,
                language=audio.parent.lang or '',
                label=audio.parent.label or '',
                codecs=audio.codecs or '',
                audio_sampling_rate=audio.audio_sampling_rate or '',
                mime_type=audio.mime_type or '',
            ))
        formats = {
            MediaName.video: videos,
        }
        if audios:
            formats[MediaName.audio] = audios
        return formats

    def select_formats(self, formats: dict) -> dict:
        video = best_video(formats[MediaName.video], **self.downloader.kwargs)
        formats[MediaName.video] = [video]
        return formats
