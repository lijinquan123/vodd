# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/15 18:59
# @Version     : Python 3.14.0
from typing import Dict, List

from vodd.core.algorithms import best_video
from vodd.core.constants import MediaName, SUPPORTED_DRM_CIPHERS
from vodd.core.models import Segment, Cipher
from vodd.format_parser.dash import tags


def get_representations(adaptation_sets: List[tags.AdaptationSet]) -> Dict[str, List[tags.Representation]]:
    representations = {}
    for adaptation_set in adaptation_sets:
        mime_type = (adaptation_set.mime_type or adaptation_set.representations[0].mime_type).split('/')[0]
        if mime_type not in representations:
            representations[mime_type] = []
        if reps := adaptation_set.representations:
            representations[mime_type].extend(reps)

    return representations


def get_video_segments(representation: tags.Representation):
    # 拼接视频切片
    segments = []
    cipher = get_cipher(representation.content_protections)
    for index, segment in enumerate(representation.segments):
        segments.append(Segment(
            type=MediaName.video,
            group_no=0,
            index=index,
            cipher=cipher,
            url=segment['segment_url'],
            duration=segment['duration'],
            init_url=segment['initialization_url'],
        ))
    return segments


def get_audios_segments(representations: List[tags.Representation]):
    audios = []
    for group_no, audio in enumerate(representations):
        segments = []
        cipher = get_cipher(audio.content_protections)
        for index, segment in enumerate(audio.segments):
            segments.append(Segment(
                type=MediaName.audio,
                group_no=group_no,
                index=index,
                url=segment['segment_url'],
                duration=segment['duration'],
                cipher=cipher,
                init_url=segment['initialization_url'],
            ))
        audios.append(segments)
    return audios


def get_cipher(content_protections: List[tags.ContentProtection]) -> Cipher:
    name = ''
    for content_protection in content_protections:
        if (name := content_protection.value.lower()) in SUPPORTED_DRM_CIPHERS:
            break
    return Cipher(name=name)
