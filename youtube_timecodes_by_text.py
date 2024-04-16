import argparse
from datetime import timedelta
from datetime import datetime
import enum
import gettext
from html import escape
from io import StringIO
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

# internal imports:
from context_manager import ContextManager
from utils import DownloadCooldownManager
from utils import get_lang_code_iso639
from utils import read_text_file_content
from vtt_to_plain_text import convert_vtt_to_text_and_timecodes
from whoosh_search import whoosh_update_index
from whoosh_search import search_with_whoosh
from yt_dlp_wrapper import download_missing_video_subtitles


def configure_localization(root_dir_path):
    if os.name == 'nt' and 'LANGUAGE' not in os.environ:
        # have to use Windows OS dependent code and set LANGUAGE env var to proper value.
        import ctypes
        import locale
        windll = ctypes.windll.kernel32
        os.environ['LANGUAGE'] = locale.windows_locale[windll.GetUserDefaultUILanguage()]

    # languages=['en', 'ru']  # Rely on one of env vars in order LANGUAGE, LC_ALL, LC_MESSAGES, LANG'
    locale_dir = root_dir_path / 'locale'
    argparse._ = gettext.translation(domain='argparse',
                                     localedir=locale_dir,
                                     fallback=True).gettext
    global _   # this module's function with name '_'
    _ = gettext.translation(domain='youtube_timecodes_by_text',
                            localedir=locale_dir,
                            fallback=True).gettext
    pass


@enum.unique
class ExitStatus(enum.IntEnum):
    success = 0
    failure = 1
    usage = 2


program_dir_path = 'to be set on launch'


def main():
    global program_dir_path
    program_dir_path = Path(sys.argv[0]).parent

    configure_localization(root_dir_path=program_dir_path)

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--query',
                        required=True,
                        help=_('A query for search. See --search_engine parameter.'))
    parser.add_argument('--search_engine',
                        help=_('default: simple case-insensitive string comparison\n'
                               'regex: Python\'s standard regular expression. '
                               'See https://docs.python.org/3/library/re.html#regular-expression-syntax\n'
                               'whoosh: Whoosh search engine. See '
                               'https://whoosh.readthedocs.io/en/latest/querylang.html'),
                        choices=['default', 'regex', 'whoosh'],
                        default='default')
    parser.add_argument('--searching_directory',
                        help=_('Path to directory where pre-downloaded youtube video subtitles are located.\n'
                               'Used only --youtube_channel_url option is not specified.\n'
                               'VTT subtitles format is supported only.\n'
                               'Json file with video information should be located in the same folder.'))
    parser.add_argument('--download_subtitles',
                        help=_('Download missing subtitles for channel before searching.\n'
                               'Warning: Slows down execution especially if Youtube throttles on too often requests.\n'
                               'Best practice is to download missing subtitles only when necessary.\n'
                               'Searching can rely on caches subtitles. Just remove this option after downloading '
                               'or use argument --subtitles_downloading_cooldown_hours.'),
                        action='store_true')
    parser.add_argument('--subtitles_language',
                        help=_('Subtitles language code. Format: ISO 639. Examples: en, ru. Default is \'ru\'.'),
                        default='ru')
    parser.add_argument('--delete_original_files_after_download',
                        help=_('Delete downloaded video info files(subtitles and json) after conversion\n'
                               'to text form to save file system space.'),
                        action='store_true',
                        default=False)
    parser.add_argument('--youtube_channel_url',
                        help=_('URL of Youtube channel to download subtitles from. '
                               'Ex: https://www.youtube.com/@galkovskyland'))
    parser.add_argument('--subtitles_cache_directory',
                        help=_('Path to root subtitles cache directory. '
                               'All downloaded subtitles will be stored there.'),
                        default='downloaded_subtitles')
    parser.add_argument('--minimize_file_system_path_length',
                        help=_('When downloading subtitles use video identifier instead of video title\n'
                               'as part of names of created files and folders.\n'
                               'Allows to avoid problem of max path length on Windows OS.'),
                        action='store_true',
                        default=False)
    parser.add_argument('--format',
                        help=_('Output format'),
                        choices=['text', 'html', 'json'],
                        default='text')
    parser.add_argument('--context_lines',
                        help=_('Total number of lines preceding and following the line that matches query'),
                        type=int,
                        default=1)
    parser.add_argument('--output',
                        help=_('Path to output file. If not specified, standard output stream is used'))
    parser.add_argument('--yt_dlp_path',
                        help=_('Path to yt-dlp tool that is used for subtitles downloading.\n'
                               'Tool can be downloaded from https://github.com/yt-dlp/yt-dlp/releases page.\n'
                               'If argument is not specified rely on PATH environment variable.'),
                        default='yt-dlp')
    parser.add_argument('--subtitles_downloading_cooldown_hours',
                        help=_('Prevents network access to Youtube for specified number of hours '
                               'after last successful downloading attempt when downloading is requested.\n'
                               'Purpose is to allow non-experienced users to use unified program arguments '
                               'and have both up to date subtitles and search attempt immediate responses'),
                        type=int,
                        default=0)
    # Whoosh search customization arguments
    w_group = parser.add_argument_group('whoosh', _('Whoosh search customization'))
    w_group.add_argument('--w:sort_by',
                         help=_('Sorting method.'),
                         choices=['upload_date', 'relevance'],
                         default='upload_date')
    w_group.add_argument('--w:results_limit',
                         help=_('Limits number of search results in each video subtitles'),
                         type=int,
                         default=99999)
    # Regex search customization arguments
    r_group = parser.add_argument_group('regex', _('Regex search customization'))
    r_group.add_argument('--r:search_on_line_edges',
                         help=_('Default search approach is to search line by line.\n'
                                'This option allows to find text split between two adjacent lines'),
                         action='store_true',
                         default=False)

    if len(sys.argv) == 1 and os.name == 'nt' and getattr(sys, 'frozen', False):  # program in form of exe file
        if show_usage_instruction_and_wait_for_key_press():
            return ExitStatus.usage

    args = parser.parse_args()

    # download missing channel video subtitles if needed.
    if args.download_subtitles:
        if args.youtube_channel_url is None:
            print(_('Option --youtube_channel_url should be specified when downloading is requested.'), file=sys.stderr)
            return ExitStatus.usage
        if args.searching_directory is not None:
            print(_('Option --searching_directory should not be specified when subtitles downloading is '
                    'requested. Argument --subtitles_cache_directory allows to change location of downloaded subtitles'
                    ), file=sys.stderr)
            return ExitStatus.usage

        channel_id = get_channel_id(args.youtube_channel_url)
        root_subtitles_directory = Path(args.subtitles_cache_directory) / channel_id

        download_manager = DownloadCooldownManager(root_subtitles_directory)
        if not download_manager.is_cooldown_active(timedelta(hours=args.subtitles_downloading_cooldown_hours)):
            subtitles_lang = get_lang_code_iso639(args.subtitles_language)
            download_missing_video_subtitles(channel_id,
                                             root_subtitles_directory,
                                             args.yt_dlp_path,
                                             args.minimize_file_system_path_length,
                                             subtitles_langs=[subtitles_lang] if subtitles_lang is not None else None)
            download_manager.save_last_successful_download_time()
    elif args.youtube_channel_url is not None:
        if args.searching_directory is not None:
            print(_('Option --searching_directory should not be specified when youtube channel is specified. '
                    'Argument --subtitles_cache_directory allows to change location of downloaded subtitles'),
                  file=sys.stderr)
            return ExitStatus.usage
        root_subtitles_directory = Path(args.subtitles_cache_directory) / get_channel_id(args.youtube_channel_url)
    elif args.searching_directory is not None:
        root_subtitles_directory = Path(args.searching_directory)
    else:
        print(_('One of following options should be specified: '
                '--searching_directory, --download_subtitles, --youtube_channel_url'), file=sys.stderr)
        return ExitStatus.usage

    remove_original_files_after_download = args.download_subtitles and args.delete_original_files_after_download

    # prepare raw text and timecodes files to be searched instead of pure vtt files.
    subtitles_text_dir_path = root_subtitles_directory / 'subs_in_text_form'
    convert_subtitles_to_text_form(root_subtitles_directory,
                                   subtitles_text_dir_path,
                                   remove_original_files_after_download)

    # search in subtitles
    match args.search_engine:
        case 'default' | 'regex':
            # print(f'query: {args.query}')
            regex_text = args.query if args.search_engine == 'regex' else re.escape(args.query)
            regex_to_search = re.compile(regex_text, re.IGNORECASE)
            regex_args = get_regex_args(args)
            context_lines = args.context_lines if not regex_args['search_on_line_edges'] or args.context_lines != 1\
                else args.context_lines + 1  # need to extend one line context when searching on the line edges.
            video_timecodes = search_with_regex(subtitles_text_dir_path,
                                                regex_to_search,
                                                context_lines,
                                                regex_args)

        case 'whoosh':
            index_dir_path = subtitles_text_dir_path / 'index'
            whoosh_update_index(subtitles_text_dir_path, index_dir_path)
            results_info_list = search_with_whoosh(subtitles_text_dir_path,
                                                   index_dir_path,
                                                   args.query,
                                                   get_whoosh_args(args))
            video_timecodes = get_timecodes_from_whoosh_results(results_info_list, args.context_lines)

        case _:
            print(_(f'Search engine {args.search_engine} is not supported'), file=sys.stderr)
            return ExitStatus.usage

    # print results
    if args.output is not None:
        output_file_path = Path(args.output)
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            print_results(video_timecodes, args.format, args.query, output_file, output_file_path)
    else:
        print_results(video_timecodes, args.format, args.query, sys.stdout)

    return ExitStatus.success


def convert_subtitles_to_text_form(input_root_path, output_root_path, remove_original_files):
    files_to_remove = []
    for subtitles_path in get_subtitles_paths_recursively(input_root_path):
        text_file_path = (output_root_path / subtitles_path.relative_to(input_root_path)).with_suffix('.txt')
        text_file_path.parent.mkdir(exist_ok=True, parents=True)
        timecodes_file_path = text_file_path.with_suffix('.timecodes.txt')

        if not text_file_path.exists() or not timecodes_file_path.exists():
            convert_vtt_to_text_and_timecodes(subtitles_path, text_file_path, timecodes_file_path)

        # copy info file to get all information in one place during actual searching
        source_info_file_path = (subtitles_path.parent / subtitles_path.stem).with_suffix('.info.json')
        target_info_file_path = output_root_path / source_info_file_path.relative_to(input_root_path)
        if not target_info_file_path.exists():
            # shutil.copy(source_info_file_path, target_info_file_path)
            # original file are pretty heavy, use shallow copy instead.
            make_shallow_copy_of_info_file(source_info_file_path, target_info_file_path)
            if remove_original_files:
                files_to_remove.append((subtitles_path, source_info_file_path))

    # remove files to save filesystem space
    for pair in files_to_remove:
        (subtitles_path, source_info_file_path) = pair
        subtitles_path.unlink()
        source_info_file_path.unlink()

        parent_dir = subtitles_path.parent
        # remove empty directory
        if not any(parent_dir.iterdir()):
            parent_dir.rmdir()
    pass


def make_shallow_copy_of_info_file(source_info_file_path, target_info_file_path):
    info = {}
    fields = ['id', 'title', 'upload_date']
    with open(source_info_file_path, 'r', encoding='utf-8') as input_file:
        orig_video_info = json.load(input_file)

        for field in fields:
            info[field] = orig_video_info[field]

    with open(target_info_file_path, 'w', encoding='utf-8') as output_file:
        json.dump(info, output_file, indent='  ', ensure_ascii=False)

    pass


def search_with_regex(input_root_path, regex_to_search, context_lines_count, args):
    # element is dict {'video_upload_date',
    #                  'video_title',
    #                  'video_id',
    #                  'timecode_info_list': [
    #                     {'timecode_seconds',
    #                      'video_url_with_timecode',
    #                      'context'
    #                      }
    #                  ]
    #                 }

    for subtitles_path in get_subtitles_in_text_form_paths_recursively(input_root_path):
        if subtitles_path.exists():
            timecodes_in_seconds = get_timecodes_from_subtitles_text_timecode_file_pair(subtitles_path,
                                                                                        regex_to_search,
                                                                                        context_lines_count,
                                                                                        args)
            if len(timecodes_in_seconds) > 0:
                info_file_path = Path(subtitles_path.parent / subtitles_path.stem).with_suffix('.info.json')
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    video_info = json.load(f)  # note: a lot of video metadata is in this dictionary if needed.
                    video_id = video_info['id']
                    video_title = video_info['title']
                    video_upload_date_str = video_info['upload_date']
                video_url = f'https://youtu.be/{video_id}'

                # print(f'{video_upload_date_str} {video_title}')
                timecode_info_list = []
                for timecode, context in timecodes_in_seconds:
                    timecode_seconds = int(timecode)
                    video_url_with_timecode = f'{video_url}?t={timecode_seconds}'
                    # print(f'    {video_url_with_timecode}')
                    timecode_info_list.append({
                        'timecode_seconds': timecode_seconds,
                        'url': video_url_with_timecode,
                        'context': context
                    })

                # convert to date just for compatibility with Whoosh search results.
                # Note: time zone defined on Youtube's date implicit timezone. Hope it is utc.
                upload_date_utc = datetime.strptime(video_upload_date_str, '%Y%m%d')

                yield dict({
                    'video_upload_date': upload_date_utc,
                    'video_title': video_title,
                    'video_id': video_id,
                    'timecode_info_list': timecode_info_list
                })
    pass


def get_timecodes_from_subtitles_text_timecode_file_pair(text_file_path,
                                                         regex_to_search,
                                                         context_lines_count,
                                                         args
                                                         ):
    timecodes = []
    duration_to_ignore_seconds = 10  # ignore time codes with short gaps

    context_manager = ContextManager(context_lines_count) if context_lines_count > 1 else None

    should_search_on_line_edges = args['search_on_line_edges']
    adjacent_line_with_no_match = None

    timecodes_path = text_file_path.with_suffix('.timecodes.txt')
    with open(text_file_path, 'r', encoding='utf-8') as text_f:
        with open(timecodes_path, 'r', encoding='utf-8') as timecodes_f:
            for line in text_f:
                if context_manager is not None:
                    context_manager.update(line)

                matched = False
                timecode_line = next(timecodes_f)  # rely on equality of line number in subtitles and timecodes files.

                if match := regex_to_search.search(line):
                    matched = True
                    # print(match)
                    if timecode_record := get_timecode_record(context_lines_count,
                                                              context_manager,
                                                              duration_to_ignore_seconds,
                                                              line,
                                                              timecode_line,
                                                              timecodes
                                                              ):
                        timecodes.append(timecode_record)
                elif should_search_on_line_edges and adjacent_line_with_no_match is not None:
                    # Search on the line edges. Text that split between lines could be missed.
                    adjacent_line_with_no_match_text = adjacent_line_with_no_match[0]
                    combined_lines_text = f'{adjacent_line_with_no_match_text} {line.strip()}'
                    if match := regex_to_search.search(combined_lines_text):
                        matched = True
                        adjacent_line_with_no_match_timecode = adjacent_line_with_no_match[1]

                        if timecode_record := get_timecode_record(context_lines_count,
                                                                  context_manager,
                                                                  duration_to_ignore_seconds,
                                                                  adjacent_line_with_no_match_text,
                                                                  adjacent_line_with_no_match_timecode,
                                                                  timecodes
                                                                  ):
                            timecodes.append(timecode_record)

                if should_search_on_line_edges:
                    adjacent_line_with_no_match = (line.strip(), timecode_line) if not matched else None

    return timecodes


# generator of timecode record used in regex and whoosh search code.
def get_timecode_record(context_lines_count,
                        context_manager,
                        duration_to_ignore_seconds,
                        line,
                        timecode_line,
                        timecodes):
    timecode_str, timecode_seconds_str = timecode_line.split()
    timecode_seconds = int(timecode_seconds_str)
    if len(timecodes) == 0 or timecode_seconds > (timecodes[-1][0] + duration_to_ignore_seconds):
        context = None
        if context_lines_count == 1:
            context = [line.strip()]
        elif context_manager is not None:
            # note: context will be updated with lines that are read further.
            context = context_manager.context_from_previous_text()
        return timecode_seconds, context
    return None


def get_timecodes_from_whoosh_results(results_info_list, context_lines_count):
    for r in results_info_list:
        (video_id, video_title,
         subtitles_path, timecodes_path, video_upload_date, fragments) = (r['video_id'],
                                                                          r['video_title'],
                                                                          r['subtitles_path'],
                                                                          r['timecodes_path'],
                                                                          r['video_upload_date'],
                                                                          r['fragments'])
        timecodes_in_seconds = get_timecodes_from_whoosh_fragments(fragments, timecodes_path, context_lines_count)

        if len(timecodes_in_seconds) > 0:
            video_url = f'https://youtu.be/{video_id}'

            # print(f'{video_upload_date} {video_title}')
            timecode_info_list = []
            for timecode, context in timecodes_in_seconds:
                timecode_seconds = int(timecode)
                video_url_with_timecode = f'{video_url}?t={timecode_seconds}'
                # print(f'    {video_url_with_timecode}')
                timecode_info_list.append({
                    'timecode_seconds': timecode_seconds,
                    'url': video_url_with_timecode,
                    'context': context
                })
            yield dict({
                'video_upload_date': video_upload_date,
                'video_title': video_title,
                'video_id': video_id,
                'timecode_info_list': timecode_info_list
            })
    pass


def get_timecodes_from_whoosh_fragments(fragments, timecodes_path, context_lines_count):
    subtitles_content = fragments[0].text  # TODO: get rid of full file in memory

    context_manager = ContextManager(context_lines_count) if context_lines_count > 1 else None

    timecodes = []
    duration_to_ignore_seconds = 10  # ignore time codes with short gaps

    with StringIO(subtitles_content) as subtitles_f:
        with open(timecodes_path, 'r', encoding='utf-8') as timecodes_f:
            for line in subtitles_f:
                if context_manager is not None:
                    context_manager.update(line)

                timecode_line = next(timecodes_f)  # rely on equality of line number in subtitles and timecodes files.

                # Rely on fact that StringIO's tell() function returns position of "offset in chars" type,
                # not number of bytes. Not ideal as docs state that units are "opaque" number, but works.
                current_line_end_pos = subtitles_f.tell()
                if current_line_end_pos <= fragments[0].startchar:
                    # fragments are sorted, skip line without enumerating fragments.
                    continue

                current_line_start_pos = current_line_end_pos - len(line)
                if current_line_start_pos > fragments[-1].endchar:
                    # skip rest of the file when context of the last fragment has gathered.
                    if context_manager is None or not context_manager.is_context_completion_pending():
                        break

                for fragment in fragments:
                    if current_line_start_pos <= fragment.startchar < current_line_end_pos:
                        if timecode_record := get_timecode_record(context_lines_count,
                                                                  context_manager,
                                                                  duration_to_ignore_seconds,
                                                                  line,
                                                                  timecode_line,
                                                                  timecodes
                                                                  ):
                            timecodes.append(timecode_record)
                            break  # TODO: can't we break when fragment found.
                                # In any case only duration_to_ignore_seconds
                                # limit can prevent adding of timecode.
                    pass

    return timecodes


def print_results(video_timecodes, format_, query_text, output_file, output_file_path=None):
    match format_:
        case 'text':
            print_results_text(video_timecodes, output_file)
        case 'html':
            print_results_html(query_text, video_timecodes, output_file, output_file_path)
        case 'json':
            print_results_json(video_timecodes, output_file)
        case _:
            raise Exception(f'output format {format_} is not supported')


def print_results_html(query_text, video_timecodes, output_file, output_file_path=None):
    css_reference_line = ''
    resources_path = program_dir_path / 'resources' / 'search_results_web_page'
    src_css_resource_path = resources_path / 'style.css'
    css_embedded = True

    if not css_embedded and output_file_path is not None:
        if src_css_resource_path.exists():
            page_resources_path = output_file_path.parent / (output_file_path.stem + '_files')
            page_resources_path.mkdir(parents=True, exist_ok=True)
            dst_src_css_resource_path = page_resources_path / src_css_resource_path.name
            import shutil
            shutil.copy(src_css_resource_path, dst_src_css_resource_path)

            css_reference_line = (f'<link rel="stylesheet" '
                                  f'href="./{dst_src_css_resource_path.parent.name}/{dst_src_css_resource_path.name}" />')

    html_templates_path = resources_path / 'html_templates'

    def write_from_template(template_name, template_args=None):
        template = read_text_file_content(html_templates_path / template_name)
        text = template
        if template_args is not None:
            for arg, value in template_args.items():
                text = text.replace(f'%{arg}%', value)
        print(text, file=output_file)

    write_from_template('header.txt', {'head_element_children': css_reference_line,
                                                               'query_text': escape(query_text),
                                                               'style': src_css_resource_path.read_text() if css_embedded else ''
                                                              })

    not_found = True

    for info in video_timecodes:
        video_upload_date, video_title, timecode_info_list = (info['video_upload_date'],
                                                              info['video_title'],
                                                              info['timecode_info_list'])
        write_from_template('video_result_header.txt',
                            {'video_title':
                                         f'{video_upload_date.strftime('%Y%m%d')} {video_title}'})
        for timecode_info in timecode_info_list:
            url, timecode_seconds, context = (timecode_info['url'],
                                              timecode_info['timecode_seconds'],
                                              timecode_info['context'])
            pretty_timestamp = str(timedelta(seconds=timecode_seconds))  # Example: 0:17:16
            context_content = f'{escape(' '.join(context))}' if context is not None else ''

            write_from_template('timecode_item.txt', {'timecode_url': url,
                                                                              'timecode_time': pretty_timestamp,
                                                                              'context': context_content
                                                                              })
        write_from_template('video_result_footer.txt')
        not_found = False

    if not_found:
        write_from_template('no_results.txt')

    write_from_template('footer.txt')
    pass


def print_results_text(video_timecodes, output_file):
    for info in video_timecodes:
        video_upload_date, video_title, timecode_info_list = (info['video_upload_date'],
                                                              info['video_title'],
                                                              info['timecode_info_list'])
        print(f'{video_upload_date.strftime('%Y%m%d')} {video_title}', file=output_file)
        for timecode_info in timecode_info_list:
            url, timecode_seconds, context = (timecode_info['url'],
                                              timecode_info['timecode_seconds'],
                                              timecode_info['context'])
            pretty_timestamp = str(timedelta(seconds=timecode_seconds))  # Example: 0:17:16
            context_text = ' '.join(context) if context is not None else ''
            print(f'    {pretty_timestamp} {url} {context_text}', file=output_file)
    pass


def print_results_json(timecode_info_list, output_file):
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y%m%d')
        raise TypeError("Type not serializable")

    timecode_info_list = [item for item in timecode_info_list]
    json.dump(timecode_info_list,
              output_file,
              indent='  ',
              ensure_ascii=False,
              default=serialize_datetime
              )


def get_channel_id(youtube_channel_url):
    url = urlparse(youtube_channel_url)
    channel_id = url.path.strip('/')
    if not channel_id.startswith('@'):
        raise ValueError('Youtube channel URL is not supported. Channel name should start with @ symbol.')
    return channel_id


def get_subtitles_in_text_form_paths_recursively(root_dir_path):
    unsorted_paths = filter(lambda p: '.timecodes' not in p.suffixes,
                            [p for p in root_dir_path.rglob('*.txt')])
    # sort by upload date saved in form of YYYYMMDD prefix in directory name
    date_prefix_len = len('YYYYMMDD')
    sorted_paths = sorted(unsorted_paths, key=lambda x: x.parent.name[:date_prefix_len], reverse=True)
    return sorted_paths


def get_subtitles_paths_recursively(root_dir_path):
    for subtitles_path in root_dir_path.rglob('*.vtt'):
        yield subtitles_path


def get_whoosh_args(args):
    return get_subsystem_args(args, prefix='w:')


def get_regex_args(args):
    return get_subsystem_args(args, prefix='r:')


def get_subsystem_args(args, prefix):
    subsystem_args = {}
    for arg in vars(args):
        if arg.startswith(prefix):
            name = arg[len(prefix):]
            value = getattr(args, arg)
            subsystem_args[name] = value
    return subsystem_args


def show_usage_instruction_and_wait_for_key_press():
    import ctypes.wintypes
    import msvcrt
    kernel32 = ctypes.WinDLL('Kernel32')
    buffer = (1 * ctypes.wintypes.DWORD)()
    attached_processes = kernel32.GetConsoleProcessList(buffer, 1)
    # If we only have a single process attached, then the executable was double clicked
    # When using `pyinstaller` with `--onefile`, two processes get attached
    is_onefile = hasattr(sys, '_MEIPASS') and os.path.basename(sys._MEIPASS).startswith('_MEI')
    if attached_processes == 1 or is_onefile and attached_processes == 2:
        print(_('Do not double-click the executable, instead call it from a command line.'), file=sys.stderr)
        msvcrt.getch()
        return True
    return False


if __name__ == '__main__':
    sys.exit(main())
