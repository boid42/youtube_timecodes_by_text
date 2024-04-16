import json
from io import TextIOWrapper
import queue
import sys
import subprocess
from time import sleep


def download_missing_video_subtitles(channel_id,
                                     channel_cache_dir_path,
                                     yt_dlp_path,
                                     minimize_file_system_path_length=False,
                                     subtitles_langs=None):
    root_path = channel_cache_dir_path.parent
    channel_cache_dir_path.mkdir(parents=True, exist_ok=True)

    download_archive_path = channel_cache_dir_path / 'ytdl-archive.txt'
    cookies_path = root_path / 'cookies.txt'

    videos_to_download = get_unhandled_channel_video_list(channel_id,
                                                          download_archive_path,
                                                          cookies_path,
                                                          yt_dlp_path)
    debug_yt_dlp_results = False

    max_simultaneous_downloads = 2
    download_queue = queue.Queue()
    pending_downloads = []

    def process_downloads():
        for pd in list(pending_downloads):
            video_id, proc = pd
            if proc.poll() is None:
                continue  # process is still running
            if proc.returncode != 0:
                raise Exception(f'Downloading of video {video_id} failed. Error code: {proc.returncode}')
            print(f'video {video_id} downloading complete')
            pending_downloads.remove(pd)

        # start next download if free slot exists.
        if not download_queue.empty() and len(pending_downloads) < max_simultaneous_downloads:
            video_id = download_queue.get()
            proc = start_video_download(video_id,
                                        root_path,
                                        download_archive_path,
                                        cookies_path,
                                        yt_dlp_path,
                                        subtitles_only=True,
                                        minimize_file_system_path_length=minimize_file_system_path_length,
                                        subtitles_langs=subtitles_langs
                                        )
            pending_downloads.append((video_id, proc))

    for video_info in videos_to_download:
        if debug_yt_dlp_results:
            with open(f'{video_info['id']}.debug.info.json', 'w', encoding='utf-8') as output_file:
                json.dump(video_info, output_file, indent='  ', ensure_ascii=False)

        status = video_info['live_status'] if 'live_status' in video_info else None
        if status is None or status == 'not_live' or status == 'was_live':
            download_queue.put(video_info['id'])
        else:
            # yt-dlp fails on attempt to download subtitles for videos with live statuses:
            #   "is_upcoming"
            #   "is_live"
            print(f'Skip live video {video_info['id']}. Status is {status}')
            pass

        # attempt to download immediately
        process_downloads()

    # download the rest of videos
    while not download_queue.empty():
        process_downloads()
        if len(pending_downloads) == max_simultaneous_downloads:
            sleep(0.1)  # save cpu.

    pass


def start_video_download(video_id,
                         root_path,
                         download_archive_path,
                         cookies_path,
                         yt_dlp_path,
                         subtitles_only,
                         minimize_file_system_path_length=False,
                         subtitles_langs=None
                         ):
    video_url = f'https://www.youtube.com/watch?v={video_id}'

    if minimize_file_system_path_length:
        # use video id (regular length is 11 characters) instead of video title that can be 90+ characters
        # in some cases. Purpose is to not exceed Window OS default 256 characters path length limit.
        output_path_template = '%(uploader_id)s/%(upload_date>%Y)s/%(upload_date)s_%(id)s/%(id)s.%(ext)s'
    else:
        output_path_template = '%(uploader_id)s/%(upload_date>%Y)s/%(upload_date)s_%(title)s/%(title)s.%(ext)s'
    if sys.platform.startswith('win'):
        output_path_template = output_path_template.replace('>', '^>')

    args = [yt_dlp_path,
            '--no-mtime',
            '--write-sub',
            '--write-auto-sub']
    if subtitles_langs is not None:
        args.extend(['--sub-lang', ','.join(subtitles_langs)])
    args.extend(['--write-info-json',
                 '--no-clean-infojson',
                 '--output', output_path_template,
                 '--paths', f'home:{root_path}',
                 '--cookies', str(cookies_path),
                 '--download-archive', str(download_archive_path)])
    if subtitles_only:
        args.extend([
            '--skip-download',
            '--force-download-archive',  # as --skip-download option is specified.
        ])

    args.append(video_url)

    # print(' '.join(args))

    process = subprocess.Popen(args,
                               shell=True,
                               stdout=sys.stdout,
                               stderr=subprocess.STDOUT
                               )

    if process.returncode is not None and process.returncode != 0:
        raise Exception(f'Command {yt_dlp_path} failed. See error description above.')
    return process


def get_unhandled_channel_video_list(channel_id, download_archive_path, cookies_path, yt_dlp_path):
    channel_url = f'https://www.youtube.com/{channel_id}'

    args = [yt_dlp_path,
            '--newline',
            '--ignore-errors',
            '--ignore-no-formats-error',  # to avoid a failure if YouTube channel
                                          # has at least one scheduled live translation videos.
            '--dump-json',
            '--cookies', str(cookies_path),
            '--download-archive', str(download_archive_path),
            channel_url]

    # print(' '.join(args))

    with subprocess.Popen(args, stdout=subprocess.PIPE, shell=True) as process:
        for line in TextIOWrapper(process.stdout, encoding="utf-8"):
            video_info_json = json.loads(line)
            print(f'new video: {video_info_json['id']}, "{video_info_json['title']}"')
            yield video_info_json

    if process.returncode is not None and process.returncode != 0:
        raise Exception(f'Command {yt_dlp_path} failed. See error description above.')

