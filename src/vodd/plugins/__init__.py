# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/9/16 12:19
# @Version     : Python 3.13.7
from vodd.plugins.__base_plugin__ import BasePlugin
from vodd.utils.probe import get_plugin_map


def get_all_plugins():
    return get_plugin_map(BasePlugin)
