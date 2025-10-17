# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/29 10:45
# @Version     : Python 3.13.7
from collections import namedtuple

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
SUPPORTED_DRM_CIPHERS = {
    # 'cenc',
    'widevine',
    # 'playready',
}
MediaName = (
    _ := namedtuple('MediaName', field_names=[
        'video',
        'audio',
        'subtitle',
    ])
)(*_._fields)
