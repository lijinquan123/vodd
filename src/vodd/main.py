# -*- coding: utf-8 -*-
# @Author      : LJQ
# @Time        : 2025/10/16 12:14
# @Version     : Python 3.14.0
import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from vodd.downloader import Downloader
from vodd.utils.args import jsonloads, commalist

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s line:%(lineno)d %(process)d-%(threadName)s-%(thread)d %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)


def build_parser():
    # -o 1.ts --url "https://hk4-edge25-1.edgeware.tvb.com/manifest.mpd" --drm-request "{\"url\": \"https://prod-inews-wv.tvb.com/wvproxy/mlicense?contentid=20251016\"}" --drm-private-key-path "private_key.pem" --drm-client-id-path "client_id.bin"
    parser = argparse.ArgumentParser(usage='VOD Downloader', description='--help')
    parser.add_argument('-c', type=str, dest='config', help='从配置文件中读取所有参数,配置参数会覆盖命令参数')
    parser.add_argument('-o', type=str, dest='save_path', help='需要保存的路径')
    parser.add_argument('-r', type=float, default=5, dest='rate', help='下载速度,实际上会略小于当前值')

    downloader = parser.add_argument_group('downloader')
    downloader.add_argument('-p', type=str, dest='plugin', help='插件名字')
    downloader.add_argument('--url', type=str, dest='url', help='播放链接')
    downloader.add_argument('--headers', dest='headers', type=jsonloads, help='播放使用的请求头')
    downloader.add_argument('--drm-request', dest='drm_request', type=jsonloads, help='请求DRM许可使用的请求数据')
    downloader.add_argument('--drm-private-key-path', type=str, dest='private_key_path', help='DRM私钥文件路径')
    downloader.add_argument('--drm-client-id-path', type=str, dest='client_id_path', help='DRM客户端ID路径')
    downloader.add_argument('--per-timeout', type=int, default=20 * 60, dest='per_timeout', help='单个切片超时时间')
    downloader.add_argument('--overall-timeout', type=int, default=2 * 60 * 60, dest='overall_timeout',
                            help='总体超时时间')
    downloader.add_argument('--max-download-times', type=int, default=3, dest='max_download_times', help='最大下载次数')
    downloader.add_argument('--chunk-size', type=int, default=1 * 1024 * 1024, dest='chunk_size',
                            help='请求或者文件保存时的分块大小')
    downloader.add_argument('--max-segment-size', type=int, default=20 * 1024 * 1024, dest='max_segment_size',
                            help='最大的切片大小,超过此值时,必须使用分块模式,防止占用内存过大')
    downloader.add_argument('--chunk-file-size', type=int, default=200 * 1024 * 1024, dest='chunk_file_size',
                            help='分块文件大小')

    selector = parser.add_argument_group('selector')
    selector.add_argument('--height', type=commalist, dest='height', default='1080,480,1080',
                          help='优先选择的分辨率(高)')
    selector.add_argument('--bandwidth', type=commalist, dest='bandwidth', default='3*1024*1024,1024,10*1024*1024',
                          help='优先选择的码率')
    selector.add_argument('--framerate', type=commalist, dest='framerate', default='25,0,120', help='优先选择的帧率')
    return parser


def main(argv: list = None):
    parser = build_parser()
    error_code = 0
    try:
        if argv is None:
            argv = sys.argv[1:]
        args, unknown = parser.parse_known_args(argv)
        if not ((args.save_path and args.url) or args.config):
            raise ValueError("缺少参数[--url,-o]或者[-c]")
        if args.config:
            # 将配置文件的参数重新赋值到命令参数中
            argv.pop(position := argv.index('-c'))
            argv.pop(position)
            return main(argv=[*argv, *json.loads(Path(args.config).read_text('utf-8'))])
        for k, v in (kwargs := vars(args)).items():
            if v == parser.get_default(k):
                continue
            logger.info(f'{k}: {v}')
        if error := (data := Downloader(**kwargs).start())['error']:
            error_code = 1
        print(f'{json.dumps(data, ensure_ascii=False)}', file=[sys.stdout, sys.stderr][bool(error)])
    except KeyboardInterrupt:
        error_code = 130
    except Exception:
        traceback.print_exc()
        error_code = 2
    sys.exit(error_code)


if __name__ == '__main__':
    main()
