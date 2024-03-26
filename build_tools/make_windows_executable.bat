call venv\Scripts\activate
:: executable file will be located at dist directory
pyinstaller --onefile youtube_timecodes_by_text.py
:: copy locale files
xcopy locale\*.mo dist\locale\ /sy
:: copy resources files
xcopy resources\*.* dist\resources\ /sy