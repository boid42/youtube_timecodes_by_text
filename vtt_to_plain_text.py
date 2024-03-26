import codecs
import webvtt


def convert_vtt_to_text_and_timecodes(input_file_path, output_text_file_path, output_index_file_path):
    transcript = timecodes = ''
    lines = []
    line_timecodes = []

    for segment in webvtt.read(input_file_path):
        # Strip the newlines from the end of the text.
        # Split the string if it has a newline in the middle
        # Add the lines to an array
        segment_lines = segment.text.strip().splitlines()
        lines.extend(segment_lines)

        timecode_pair = (int(segment.start_in_seconds),
                         segment.start[:-4])  # drop fractional part from timecode in form '00:00:00.123'
        segment_line_timecodes = ([timecode_pair]
                                  * len(segment_lines))  # number of timecode lines should match number of content lines
        line_timecodes.extend(segment_line_timecodes)

    # Remove repeated lines
    previous = None
    for line_number, line in enumerate(lines):
        if line == previous:
            continue

        transcript += line + '\n'
        timestamp_seconds, timestamp_str = line_timecodes[line_number]
        timecodes += f'{timestamp_str} {timestamp_seconds}\n'
        previous = line

    save_to_utf8_text_file(output_text_file_path, transcript)
    save_to_utf8_text_file(output_index_file_path, timecodes)
    pass


def save_to_utf8_text_file(path, text):
    with codecs.open(path, 'w', 'utf-8') as f:
        f.write(text)
