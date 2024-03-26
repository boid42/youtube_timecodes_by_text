from datetime import datetime
import json
from pathlib import Path
from whoosh.fields import Schema, ID, TEXT, NUMERIC, DATETIME
from whoosh.index import create_in
from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from whoosh.qparser import GtLtPlugin
from whoosh.lang.snowball.russian import RussianStemmer
from whoosh.analysis import StemmingAnalyzer
from whoosh.highlight import Formatter
from whoosh.highlight import PinpointFragmenter
from whoosh.sorting import FieldFacet

import utils

# for enforcing of index recreation on breaking changes in index scheme.
index_schema_version = '1'


# returns raw fragments
class ZeroFormatter(Formatter):
    def format(self, fragments, replace=False):
        return fragments


def search_with_whoosh(content_root_path, index_dir_path, query_text, args):
    # print(whoosh.index.version_in(index_dir_path))

    ix = open_dir(index_dir_path)

    # print(f'whoosh index release and version: {ix.release}, {ix.version}')

    with (ix.searcher() as searcher):
        content_field_name = 'content'

        query_parser = QueryParser(content_field_name, ix.schema)
        query_parser.add_plugin(GtLtPlugin())

        # print(f'query text: {query_text}')
        query = query_parser.parse(query_text)  # ,debug=True

        sort_facets = []
        match args['sort_by']:
            case 'upload_date':
                sort_facets.append(FieldFacet('date', reverse=True))

        results = searcher.search(query,
                                  limit=None,
                                  terms=True,  # terms for speed up highlighting
                                  sortedby=sort_facets)

        # print(f'found {len(results)} results. {results}')
        # for hit in results:
        #     print(f'  {hit['path']}')

        results.formatter = ZeroFormatter()
        results.fragmenter = PinpointFragmenter(surround=0,
                                                charlimit=None)
        for hit in results:
            # print(hit)

            subtitles_path = content_root_path / hit['path']
            subtitles_content = subtitles_path.read_text(encoding='utf-8')  # TODO: try to stream it.

            fragments = hit.highlights(fieldname=content_field_name,
                                       text=subtitles_content,
                                       top=args['results_limit'])
            # print(fragments)
            # for f in fragments:
            #     print(f'fragment [{f.startchar}:{f.endchar}]: {f.text[f.startchar:f.endchar]}')

            if len(fragments) > 0:
                timecodes_path = content_root_path / hit['timecodes_path']
                yield dict({
                    'video_id': hit['id'],
                    'video_title': hit['title'],
                    'video_upload_date': hit['date'],
                    'subtitles_path': subtitles_path,
                    'timecodes_path': timecodes_path,
                    'fragments': fragments
                            })
            else:
                # print(f'hit with zero fragments: {hit}')
                pass  # happens if fragmenter's char limit is too small.
    pass


def whoosh_update_index(content_root_path, index_dir_path, clean=False):
    if not index_dir_path.exists():
        clean = True

    if utils.read_text_file_content(index_dir_path / 'schema.version') != index_schema_version:
        clean = True

    if clean:
        create_index(content_root_path, index_dir_path)
    else:
        update_index_incrementally(content_root_path, index_dir_path)


def update_index_incrementally(content_root_path, index_dir_path):
    ix = open_dir(index_dir_path)

    # The set of all paths in the index
    indexed_paths = set()
    # The set of all paths we need to re-index
    to_index = set()

    with ix.searcher() as searcher:
        writer = ix.writer()

        # Loop over the stored fields in the index
        for fields in searcher.all_stored_fields():
            indexed_path = fields['path']
            indexed_paths.add(Path(indexed_path))

            index_path_full = (content_root_path / indexed_path)
            if not index_path_full.exists():
                # This file was deleted since it was indexed
                writer.delete_by_term('path', indexed_path)
            else:
                # Check if this file was changed since it was indexed
                indexed_time = fields['time']
                mtime = index_path_full.stat().st_mtime
                if mtime > indexed_time:
                    # The file has changed, delete it and add it to the list of files to reindex
                    writer.delete_by_term('path', indexed_path)
                    to_index.add(indexed_path)

        # Loop over the files in the filesystem
        for path in get_subtitles_in_text_form_paths_recursively(content_root_path):
            if path in to_index or path.relative_to(content_root_path) not in indexed_paths:
                # This is either a file that's changed, or a new file that wasn't indexed before. So index it!
                add_file_to_index(content_root_path, path, writer)

        writer.commit()
    pass


def create_index(content_root_path, index_dir_path):
    stemmer_ru = RussianStemmer()
    analyzer = StemmingAnalyzer(stemfn=stemmer_ru.stem)

    # Reminder: if schema is updated in a way that existing indexes become invalid(cause crashes, can't be read, etc),
    # increment value of "index_schema_version" at the top of this file.
    # This will force upgraded app to rebuild existing incompatible index.
    schema = Schema(title=TEXT(analyzer=analyzer, stored=True),
                    id=TEXT(stored=True),
                    date=DATETIME(stored=True, sortable=True),
                    content=TEXT(analyzer=analyzer, chars=True),  # save chars for speed up pinpoint highlighting.
                    path=ID(stored=True),
                    timecodes_path=ID(stored=True),
                    time=NUMERIC(stored=True)  # for incremental update of the index.
                    )

    index_dir_path.mkdir(parents=True, exist_ok=True)
    ix = create_in(index_dir_path, schema)

    writer = ix.writer()
    for text_file_path in get_subtitles_in_text_form_paths_recursively(content_root_path):
        add_file_to_index(content_root_path, text_file_path, writer)
    writer.commit()

    utils.save_text_file_content(get_schema_version_file_path(index_dir_path), index_schema_version)

    pass


def add_file_to_index(content_root_path, text_file_path, writer):
    timecodes_file_path = text_file_path.with_suffix('.timecodes.txt')
    info_file_path = Path(text_file_path.parent / text_file_path.stem).with_suffix('.info.json')
    file_path_to_index = text_file_path
    content_to_index = file_path_to_index.read_text(encoding='utf-8')  # warning: full file content loading.
    with open(info_file_path, 'r', encoding='utf-8') as info_json_f:
        video_info = json.load(info_json_f)  # note: a lot of video metadata is in this dictionary if needed.

        file_path_to_index_rel = file_path_to_index.relative_to(content_root_path)
        timecodes_path_rel = timecodes_file_path.relative_to(content_root_path)

        date_utc = datetime.strptime(video_info['upload_date'], '%Y%m%d')

        writer.add_document(title=video_info['title'],
                            id=video_info['id'],
                            date=date_utc,
                            content=content_to_index,
                            path=str(file_path_to_index_rel),
                            timecodes_path=str(timecodes_path_rel),
                            time=text_file_path.stat().st_mtime
                            )
    pass


def get_subtitles_in_text_form_paths_recursively(root_dir_path):
    for txt_file_path in root_dir_path.rglob('*.txt'):
        if '.timecodes' not in txt_file_path.suffixes:  # skip .timecodes.txt files
            yield txt_file_path


def get_schema_version_file_path(index_dir_path):
    return index_dir_path / 'schema.version'

