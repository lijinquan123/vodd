# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/16 12:14
# @Version     : Python 3.14.0
import argparse
import logging
import sys
import traceback

from vodd.downloader import Downloader
from vodd.utils.args import jsonloads, commalist

logger = logging.getLogger(__name__)


def main():
    # -p 1.ts --url "https://hk4-edge25-1.edgeware.tvb.com/manifest.mpd" --drm-request "{\"url\": \"https://prod-inews-wv.tvb.com/wvproxy/mlicense?contentid=20251016\"}" --drm-private-key-path "private_key.pem" --drm-client-id-path "client_id.bin"
    parser = argparse.ArgumentParser(usage='VOD Downloader', description=' --help')
    parser.add_argument('-p', '--path', type=str, required=True, dest='save_path', help='需要保存的路径')
    parser.add_argument('-s', '--speed', required=False, type=float, default=5, dest='speed',
                        help='下载速度，实际上会略小于当前值')

    plugin = parser.add_argument_group('plugin')
    plugin.add_argument('--name', required=False, type=str, dest='name', help='插件名字')
    plugin.add_argument('--url', required=True, type=str, dest='url', help='播放链接')
    plugin.add_argument('--headers', required=False, dest='headers', type=jsonloads, help='播放使用的请求头')
    plugin.add_argument('--drm-request', required=False, dest='drm_request', type=jsonloads,
                        help='请求DRM许可使用的请求数据')
    plugin.add_argument('--drm-private-key-path', required=False, type=str, dest='private_key_path',
                        help='DRM私钥文件路径')
    plugin.add_argument('--drm-client-id-path', required=False, type=str, dest='client_id_path',
                        help='DRM客户端ID路径')
    plugin.add_argument('--height', required=False, type=commalist, dest='height', default='1080,480,1080',
                        help='优先选择的分辨率(高)')
    plugin.add_argument('--bandwidth', required=False, type=commalist, dest='bandwidth',
                        default='3*1024*1024,1024,10*1024*1024', help='优先选择的码率')
    plugin.add_argument('--framerate', required=False, type=commalist, dest='framerate', default='25,0,120',
                        help='优先选择的帧率')
    download = parser.add_argument_group('download')
    download.add_argument('--per-timeout', type=int, default=3 * 60, required=False, dest='per_timeout',
                          help='单个切片超时时间')
    download.add_argument('--overall-timeout', type=int, default=1 * 60 * 60, required=False, dest='overall_timeout',
                          help='总体超时时间')
    download.add_argument('--max-download-times', type=int, default=3, required=False, dest='max_download_times',
                          help='最大下载次数')
    download.add_argument('--chunk-size', type=int, default=1 * 1024 * 1024, required=False, dest='chunk_size',
                          help='请求或者文件保存时的分块大小')
    download.add_argument('--max-segment-size', type=int, default=20 * 1024 * 1024, required=False,
                          dest='max_segment_size', help='最大的切片大小,超过此值时,必须使用分块模式,防止占用内存过大')

    error_code = 0
    try:
        args, unknown = parser.parse_known_args(sys.argv[1:])
        if not args.url and not args.update_api:
            raise ValueError("至少应提供播放链接或者更新接口")

        for k, v in (kwargs := vars(args)).items():
            if v == parser.get_default(k):
                continue
            logger.info(f'{k}: {v}')
        Downloader(**kwargs).start()
    except (KeyboardInterrupt, Exception):
        traceback.print_exc()
        error_code = 130
    sys.exit(error_code)


if __name__ == '__main__':
    main()
