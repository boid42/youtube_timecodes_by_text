import datetime
from pathlib import Path


class DownloadCooldownManager:
    timestamp_format = '%Y%m%d %H:%M:%S UTC'
    timestamp_timezone = datetime.UTC

    def __init__(self, root_path):
        self.timestamp_file_path = root_path / 'last_successful_download_timestamp'

    def is_cooldown_active(self, cooldown_timedelta):
        cooldown_expiration = self.get_last_successful_download_time_() + cooldown_timedelta
        return self.datetime_now() < cooldown_expiration

    def save_last_successful_download_time(self):
        self.save_last_successful_download_time_(self.datetime_now())

    def datetime_now(self):
        return datetime.datetime.now(self.timestamp_timezone)

    def get_last_successful_download_time_(self):
        if date_str := read_text_file_content(self.timestamp_file_path):
            timestamp_offset_naive = datetime.datetime.strptime(date_str.strip(), self.timestamp_format)
            timestamp = timestamp_offset_naive.replace(tzinfo=self.timestamp_timezone)
            return timestamp
        return datetime.datetime.min.replace(tzinfo=self.timestamp_timezone)

    def save_last_successful_download_time_(self, timestamp):
        date_str = datetime.datetime.strftime(timestamp, self.timestamp_format)
        save_text_file_content(self.timestamp_file_path, date_str)


def read_text_file_content(path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return None


def save_text_file_content(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
