# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 15:43
# @Version     : Python 3.14.0
import argparse
import base64
import json


def commalist(values):
    return [eval(v, {"__builtins__": None}, {}) for val in values.split(',') if (v := val.strip())]


def jsonloads(x):
    return json.loads(x)


def b64decode(x):
    try:
        y = base64.urlsafe_b64decode(x).decode('utf-8')
    except (UnicodeDecodeError, Exception):
        y = x
    return y.strip()


def boolean(value):
    truths = ['yes', '1', 'true', 'on']
    falses = ['no', '0', 'false', 'off']
    if value.lower() not in truths + falses:
        raise argparse.ArgumentTypeError('{0} was not one of {{{1}}}'.format(
            value, ', '.join(truths + falses)))

    return value.lower() in truths
