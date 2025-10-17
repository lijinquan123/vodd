# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/11 16:51
# @Version     : Python 3.14.0
import importlib
import inspect
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_plugin_map(base_cls: type, filter_stems: tuple = None, module: str = None):
    cls_file = Path(inspect.getfile(base_cls))
    if module is None:
        module = base_cls.__module__
        if cls_file.stem != '__init__' and module[-len(cls_file.stem):] == cls_file.stem:
            module = module[:-len(cls_file.stem) - 1]
    if filter_stems is None:
        filter_stems = '__init__', cls_file.stem
    for file in cls_file.parent.iterdir():
        if file.is_file() and file.suffix == '.py' and file.stem not in filter_stems:
            try:
                importlib.import_module(f'{module}.{file.stem}')
            except Exception as e:
                logger.exception(e)
    plugin_map = {}

    def add_plugin(cls):
        usable = getattr(cls, 'usable', None)
        if not usable:
            return False
        provider = getattr(cls, 'provider', None)
        if not isinstance(provider, str):
            provider = cls.__module__.rsplit('.', 1)[-1]
        plugin_map[provider] = cls
        return True

    def fill_support_plugin(cls):
        if not add_plugin(cls):
            return
        for subclass in cls.__subclasses__():
            if not add_plugin(subclass):
                continue
            if subclass.__subclasses__():
                fill_support_plugin(subclass)

    fill_support_plugin(base_cls)
    return dict(sorted(plugin_map.items(), key=lambda x: x[0]))
