# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/29 15:45
# @Version     : Python 3.13.7


class DownloadException(Exception):
    """下载异常"""

    def __init__(self, reason: str = None):
        self.message = type(self).__name__
        self.reason = reason
        super().__init__(self.__dict__)


class DownloadTaskError(DownloadException):
    """下载任务错误"""


class ReachMaxDownloadLimitError(DownloadException):
    """达到最大下载限制错误"""


class NotFoundError(DownloadException):
    """未找到错误"""


class CheckError(DownloadException):
    """检查错误"""


class CheckVideoError(DownloadException):
    """检查视频错误"""


class DTSCheckError(CheckVideoError):
    """DTS检查错误"""


class UnsupportedError(DownloadException):
    """不支持的错误"""


class ResolutionTooHighError(CheckVideoError):
    """分辨率过高错误"""


class ResolutionTooLowError(CheckVideoError):
    """分辨率过低错误"""


class BandwidthTooHighError(CheckVideoError):
    """带宽过高错误"""


class BandwidthTooLowError(CheckVideoError):
    """带宽过低错误"""


class FramerateTooHighError(CheckVideoError):
    """帧率过高错误"""


class FramerateTooLowError(CheckVideoError):
    """帧率过低错误"""


class SoftwareError(DownloadException):
    """软件错误"""


class FFmpegNotFoundError(SoftwareError, NotFoundError):
    """FFmpeg未找到错误"""


class MediaReaderError(DownloadException):
    """媒体读取错误"""


class URLError(MediaReaderError):
    """链接错误"""


class PlaylistError(URLError):
    """播放清单错误"""


class HTTPStatusCodeError(URLError):
    """状态码错误"""


class MediaDecrypterError(DownloadException):
    """媒体解密错误"""


class DRMLicenseError(MediaDecrypterError):
    """DRM许可错误"""


class DRMDecryptionError(MediaDecrypterError):
    """DRM解密错误"""


class MediaMergeError(DownloadException):
    """媒体合并错误"""
