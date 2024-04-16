��          �               �  2   �  s   �  o   T  H   �  [    7   i  p   �  �     �   �  O   v     �  �   �  E   �  V     �   e    -	     L
     g
  L   w
  I   �
  ]     �   l          8  =  9  e   w  �   �  O  �  �   �  $  �  r   �  �   #  P  �  I  (  �   r  .     �  6  �     �   �  R    !  �  [   �      P   �   q   �   �   �   �!  �  "  8   �#  �  �#   A query for search. See --search_engine parameter. Default search approach is to search line by line.
This option allows to find text split between two adjacent lines Delete downloaded video info files(subtitles and json) after conversion
to text form to save file system space. Do not double-click the executable, instead call it from a command line. Download missing subtitles for channel before searching.
Warning: Slows down execution especially if Youtube throttles on too often requests.
Best practice is to download missing subtitles only when necessary.
Searching can rely on caches subtitles. Just remove this option after downloading or use argument --subtitles_downloading_cooldown_hours. Limits number of search results in each video subtitles One of following options should be specified: --searching_directory, --download_subtitles, --youtube_channel_url Option --searching_directory should not be specified when subtitles downloading is requested. Argument --subtitles_cache_directory allows to change location of downloaded subtitles Option --searching_directory should not be specified when youtube channel is specified. Argument --subtitles_cache_directory allows to change location of downloaded subtitles Option --youtube_channel_url should be specified when downloading is requested. Output format Path to directory where pre-downloaded youtube video subtitles are located.
Used only --youtube_channel_url option is not specified.
VTT subtitles format is supported only.
Json file with video information should be located in the same folder. Path to output file. If not specified, standard output stream is used Path to root subtitles cache directory. All downloaded subtitles will be stored there. Path to yt-dlp tool that is used for subtitles downloading.
Tool can be downloaded from https://github.com/yt-dlp/yt-dlp/releases page.
If argument is not specified rely on PATH environment variable. Prevents network access to Youtube for specified number of hours after last successful downloading attempt when downloading is requested.
Purpose is to allow non-experienced users to use unified program arguments and have both up to date subtitles and search attempt immediate responses Regex search customization Sorting method. Subtitles language code. Format: ISO 639. Examples: en, ru. Default is 'ru'. Total number of lines preceding and following the line that matches query URL of Youtube channel to download subtitles from. Ex: https://www.youtube.com/@galkovskyland When downloading subtitles use video identifier instead of video title
as part of names of created files and folders.
Allows to avoid problem of max path length on Windows OS. Whoosh search customization default: simple case-insensitive string comparison
regex: Python's standard regular expression. See https://docs.python.org/3/library/re.html#regular-expression-syntax
whoosh: Whoosh search engine. See https://whoosh.readthedocs.io/en/latest/querylang.html Project-Id-Version: PACKAGE VERSION
POT-Creation-Date: 2024-02-25 06:58+0300
PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE
Last-Translator: FULL NAME <EMAIL@ADDRESS>
Language-Team: LANGUAGE <LL@li.org>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
Generated-By: pygettext.py 1.5
 Поисковый запрос. Смотрите описание аргумента --search_engine По-умолчанию, поиск происходит в каждой строке.
Данный аргумент позволяет искать на границе соседних строк Удалить скачанные файлы, связанные с видео(субтитры и json файл информации о видео),
после преобразования субтитров в текстовую форму, чтобы сохранить свободное место файловой системы. Не запускайте программу двойным кликом мыши. Требуется запуск из командной строки. Скачать недостающие субтитры всех видео youtube канала перед поиском.
Внимание: замедляет выполнение запроса, особенно в случае, когда Youtube активирует троттлинг при частых запросах.
Скачивание рекомендуется выполнять только при необходимости.
Рекомендуется выполнять поиск в закэшированных субтитрах. Просто удалите этот аргумент после скачивания
или воспользуйтесь аргументом --subtitles_downloading_cooldown_hours, чтобы выполнять обращение к youtube реже. Ограничивает количество результатов в каждом файле субтитров Необходимо указать как минимум один из следующих аргументов: --searching_directory, --download_subtitles, --youtube_channel_url Аргумент --searching_directory не должен быть указан, так как запрошено скачивание субтитров. Вместо этого можно изменить директорию для скачанных субтитров с помощью аргумента --subtitles_cache_directory Аргумент --searching_directory не должен быть указан, так как указана ссылка на youtube канал. Вместо этого можно изменить директорию для скачанных субтитров с помощью аргумента --subtitles_cache_directory Аргумент --youtube_channel_url должен быть указан, так как запрошено скачивание субтитров. Формат результата поиска Путь к директории, где расположены заранее скачанные youtube видео субтитры.
Используется только, когда не указан аргумент --youtube_channel_url.
Единственный поддерживаемый формат субтитров - VTT.
Файл json с информацией о видео должен быть расположен рядом с файлом субтитров. Путь для сохранения файла с результатом поиска. Если аргумент не указан, результат направляется в стандартный вывод Путь к директории кэша субтитров. Все скачанные субтитры будут сохранены здесь. Путь к утилите yt-dlp, которая используется для скачивания субтитров.
Скачать/обновить ее можно по адресу https://github.com/yt-dlp/yt-dlp/releases 
Если аргумент не указан, используется переменная среды PATH Предотвращает обращение к youtube в течение указанного количества часов после последнего успешного скачивания субтитров.
Позволяет неопытным пользователям пользоваться унифицированным набором аргументов, чтобы всегда искать по самым свежим субтитрам без задержек, связанных с сетевыми запросами Настройка поиска с помощью регулярного выражения Метод сортировки. Язык скачиваемых субтитров в формате ISO 639. Примеры: ru, en. По-умолчанию: ru. Количество строк текста субтитров до и после строки, удовлетворяющей запросу Ссылка на Youtube канал, откуда будут скачаны субтитры. Пример: https://www.youtube.com/@galkovskyland При скачивании субтитров использовать идентификатор вместо названия видео как часть имени создаваемых файлов и директорий.
Позволяет обойти проблему ограничения длины пути файловой системы по-умолчанию в операционной системе Windows Настройка поиска с помощью Whoosh Метод поиска:
    default: простое сравнение строк без учета регистра
    regex: стандартное регулярное выражение языка Питон. Справка: https://docs.python.org/3/library/re.html#regular-expression-syntax
    whoosh: поисковый движок Whoosh. Справка: https://whoosh.readthedocs.io/en/latest/querylang.html 