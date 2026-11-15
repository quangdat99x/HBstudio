"""
Tải một URL bằng engine của YouTube Downloader (cookie, JS runtime, đổi IP dongle,
tự cập nhật yt-dlp) — để Video Watcher không phải tự xử lý chuyện chống bot.

    python yt_fetch.py <downloader_dir> <url> <out_dir> [max_res]
Dòng cuối stdout là JSON: {success, filepath, info|error}
"""
import json
import os
import sys


def main():
    dl_dir, url, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    max_res = sys.argv[4] if len(sys.argv) > 4 else '720p'
    os.chdir(dl_dir)
    sys.path.insert(0, dl_dir)
    from core import engine  # noqa: E402  (config.py của Downloader nằm trong dl_dir)
    import yt_dlp

    keys = ('title', 'uploader', 'channel', 'view_count', 'like_count', 'comment_count',
            'upload_date', 'description', 'tags', 'webpage_url', 'duration')
    info = {}

    def _extract(patch):
        opts = engine._base_opts()
        opts.update(patch)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        full, _err = engine._run_with_sources(_extract)
        if full:
            info = {k: full.get(k) for k in keys if full.get(k) is not None}
            if info.get('description'):
                info['description'] = info['description'][:1500]
    except Exception:
        pass  # metadata chỉ là phần thêm; vẫn thử tải

    os.makedirs(out_dir, exist_ok=True)
    res = engine.download_video('watcher', url, out_dir, max_res, 'source', None)
    res['info'] = info
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
