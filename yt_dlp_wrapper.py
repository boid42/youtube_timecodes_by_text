import json
import sys
import subprocess
from io import TextIOWrapper


def download_missing_video_subtitles(channel_id, channel_cache_dir_path, yt_dlp_path,
                                     minimize_file_system_path_length=False):
    root_path = channel_cache_dir_path.parent
    channel_cache_dir_path.mkdir(parents=True, exist_ok=True)

    download_archive_path = channel_cache_dir_path / 'ytdl-archive.txt'
    cookies_path = root_path / 'cookies.txt'

    videos_to_download = get_unhandled_channel_video_list(channel_id,
                                                          download_archive_path,
                                                          cookies_path,
                                                          yt_dlp_path)

    for video_info in videos_to_download:
        download_video(video_info['id'],
                       root_path,
                       download_archive_path,
                       cookies_path,
                       yt_dlp_path,
                       subtitles_only=True,
                       minimize_file_system_path_length=minimize_file_system_path_length)


def download_video(video_id, root_path, download_archive_path, cookies_path, yt_dlp_path,
                   subtitles_only,
                   subtitles_langs=['ru'],  # TODO: support other languages
                   minimize_file_system_path_length=False
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
            '--write-auto-sub',
            '--sub-lang', ','.join(subtitles_langs),
            '--write-info-json',
            '--no-clean-infojson',
            '--output', output_path_template,
            '--paths', f'home:{root_path}',
            '--cookies', str(cookies_path),
            '--download-archive', str(download_archive_path)]

    if subtitles_only:
        args.extend([
            '--skip-download',
            '--force-download-archive',  # as --skip-download option is specified.
        ])

    args.append(video_url)

    # print(' '.join(args))

    subprocess.run(args, shell=True, check=True)
    pass


def get_unhandled_channel_video_list(channel_id, download_archive_path, cookies_path, yt_dlp_path):
    channel_url = f'https://www.youtube.com/{channel_id}'

    args = [yt_dlp_path,
            '--newline',
            '--ignore-errors',
            '--dump-json',
            '--cookies', str(cookies_path),
            '--download-archive', str(download_archive_path),
            channel_url]

    # print(' '.join(args))

    video_info_list = []
    with subprocess.Popen(args, stdout=subprocess.PIPE, shell=True) as process:
        for line in TextIOWrapper(process.stdout, encoding="utf-8"):
            video_info_json = json.loads(line)
            print(f'new video: {video_info_json['id']}, "{video_info_json['title']}"')
            video_info_list.append(video_info_json)

    if process.returncode is not None and process.returncode != 0:
        raise Exception(f'Command {yt_dlp_path} failed. See error description above.')

    return video_info_list  # TODO: better to allow handling of channel videos one by one
                            # to allow incremental download in case of network errors
