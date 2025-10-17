# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/6/26 17:33
# @Version     : Python 3.6.8
import inspect

import requests

from vodd.core.constants import USER_AGENT

_REQUEST_PARAMS = set(inspect.signature(requests.Session().request).parameters.keys())


def get_request_kwargs(with_url: bool = False, **kwargs):
    request_kwargs = {k: v for k, v in kwargs.items() if k in _REQUEST_PARAMS}
    if not with_url:
        request_kwargs.pop('url', None)
    request_kwargs['timeout'] = request_kwargs.get('timeout', 30)
    request_kwargs['headers'] = format_headers(kwargs.get('headers', {}))
    return request_kwargs


def format_headers(headers: dict) -> dict:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if 'user-agent' not in headers:
        headers['user-agent'] = USER_AGENT
    return headers
