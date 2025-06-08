@echo off
setlocal EnableDelayedExpansion

rem === Handle Arguments: --quiet and --log ===
set "QUIET=1"
set "LOG=1"
for %%A in (%*) do (
    if "%%~A"=="--quiet" set "QUIET=1"
    if "%%~A"=="--log" set "LOG=1"
)

rem === Define Paths ===
set "APP_BASE_DIR=%APPDATA%\UltimateMediaRenamer"
set "TEMP_DIR=%APP_BASE_DIR%\.temp"
set "TOOLS_DIR=%APP_BASE_DIR%\Tools"
set "PYTHON_EMBED_INSTALL_DIR=%TOOLS_DIR%\Python"
set "LOG_DIR=%APP_BASE_DIR%\Logs"

if "%LOG%"=="1" (
    mkdir "%LOG_DIR%" >nul 2>&1
    for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "LOGFILE=%LOG_DIR%\setup_%%A.log"
)

rem === Logging Helper Macro ===
set ">>LOG=>> !LOGFILE! 2>&1"
set "ECHOLOG=if not !QUIET!==1 echo "

rem === Start Message ===
if not "%QUIET%"=="1" (
    echo Automating UltimateMediaRenamer Setup...
)

rem === Step 1: Create .temp directory ===
mkdir "%TEMP_DIR%" >nul 2>&1
if not exist "%TEMP_DIR%" (
    %ECHOLOG% Error: Failed to create temporary directory. Exiting.
    goto :eof
)

rem === Step 2: Download Python Embedded ===
%ECHOLOG% Fetching latest Python Embedded...
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command ^
  "$url = 'https://www.python.org/downloads/windows/'; ^
   $html = Invoke-WebRequest -Uri $url; ^
   $link = $html.Links | Where-Object { $_.innerText -eq 'Download Windows embeddable package (64-bit)' } | Select-Object -First 1; ^
   if ($link) { 'https://www.python.org' + $link.href } else { '' }"`) do (
   set "PYTHON_EMBED_ZIP_URL=%%A"
)
if not defined PYTHON_EMBED_ZIP_URL (
    %ECHOLOG% Error: Failed to detect Python URL.
    goto :cleanup
)
for %%A in ("%PYTHON_EMBED_ZIP_URL%") do set "PYTHON_EMBED_ZIP_NAME=%%~nxA"
set "PYTHON_EMBED_ZIP_PATH=%TEMP_DIR%\%PYTHON_EMBED_ZIP_NAME%"
powershell -Command "Invoke-WebRequest -Uri '!PYTHON_EMBED_ZIP_URL!' -OutFile '!PYTHON_EMBED_ZIP_PATH!'" %>>LOG%
mkdir "%PYTHON_EMBED_INSTALL_DIR%" >nul 2>&1
powershell -Command "Expand-Archive -Path '!PYTHON_EMBED_ZIP_PATH!' -DestinationPath '!PYTHON_EMBED_INSTALL_DIR!' -Force" %>>LOG%

rem === Step 3: Add to PATH ===
for /f "tokens=*" %%a in ('reg query "HKCU\Environment" /v Path ^| find "Path"') do set "CURRENT_USER_PATH=%%a"
set "CURRENT_USER_PATH=!CURRENT_USER_PATH:*REG_SZ =!"
echo !CURRENT_USER_PATH! | findstr /i /c:"!TOOLS_DIR!" >nul
if errorlevel 1 (
    setx PATH "!CURRENT_USER_PATH!;!TOOLS_DIR!" >nul
    set "CURRENT_USER_PATH=!CURRENT_USER_PATH!;!TOOLS_DIR!"
)
echo !CURRENT_USER_PATH! | findstr /i /c:"!PYTHON_EMBED_INSTALL_DIR!" >nul
if errorlevel 1 (
    setx PATH "!CURRENT_USER_PATH!;!PYTHON_EMBED_INSTALL_DIR!" >nul
)

rem === Step 4: Install pip ===
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '!PYTHON_EMBED_INSTALL_DIR!\get-pip.py'" %>>LOG%
"!PYTHON_EMBED_INSTALL_DIR!\python.exe" "!PYTHON_EMBED_INSTALL_DIR!\get-pip.py" %>>LOG%

rem === Step 5: Install requirements.txt ===
if exist "requirements.txt" (
    "!PYTHON_EMBED_INSTALL_DIR!\python.exe" -m pip install -r requirements.txt %>>LOG%
)

rem === Step 6: Install ExifTool ===
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command ^
  "$url = 'https://exiftool.org/'; ^
   $html = Invoke-WebRequest -Uri $url; ^
   $match = $html.Links | Where-Object { $_.href -match 'exiftool-\d+\.\d+_64\.zip$' } | Select-Object -First 1; ^
   if ($match) { 'https://exiftool.org/' + $match.href } else { '' }"`) do (
   set "EXIFTOOL_URL=%%A"
)
for %%A in ("%EXIFTOOL_URL%") do set "EXIFTOOL_ZIP_NAME=%%~nxA"
set "EXIFTOOL_ZIP_PATH=%TEMP_DIR%\%EXIFTOOL_ZIP_NAME%"
set "EXIFTOOL_EXTRACT_DIR=%TEMP_DIR%\exiftool_extract"
powershell -Command "Invoke-WebRequest -Uri '!EXIFTOOL_URL!' -OutFile '!EXIFTOOL_ZIP_PATH!'" %>>LOG%
powershell -Command "Expand-Archive -Path '!EXIFTOOL_ZIP_PATH!' -DestinationPath '!EXIFTOOL_EXTRACT_DIR!' -Force" %>>LOG%
for /d %%D in ("!EXIFTOOL_EXTRACT_DIR!\exiftool-*") do (
    xcopy "%%D\*" "!TOOLS_DIR!\" /e /y /q >nul
)
if exist "!TOOLS_DIR!\exiftool(-k).exe" (
    del /f /q "!TOOLS_DIR!\exiftool.exe" >nul 2>&1
    ren "!TOOLS_DIR!\exiftool(-k).exe" "exiftool.exe"
)

rem === Step 7: Install FFmpeg ===
set "FFMPEG_ZIP_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
set "FFMPEG_ZIP_PATH=%TEMP_DIR%\ffmpeg.zip"
set "FFMPEG_EXTRACT_DIR=%TEMP_DIR%\ffmpeg_extract"
curl -L "%FFMPEG_ZIP_URL%" -o "%FFMPEG_ZIP_PATH%" %>>LOG%
powershell -Command "Expand-Archive -Path '%FFMPEG_ZIP_PATH%' -DestinationPath '%FFMPEG_EXTRACT_DIR%' -Force" %>>LOG%
for /r "%FFMPEG_EXTRACT_DIR%" %%F in (ffmpeg.exe ffprobe.exe) do (
    move /Y "%%F" "%TOOLS_DIR%\%%~nxF" >nul
)

rem === Step 8: Install MediaInfo ===
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command ^
  "$url = 'https://mediaarea.net/en/MediaInfo/Download/Windows'; ^
   $html = Invoke-WebRequest -Uri $url; ^
   $match = $html.Links | Where-Object { $_.href -match 'MediaInfo_CLI_\d+\.\d+_Windows_x64\.zip$' } | Select-Object -First 1; ^
   if ($match) { 'https://mediaarea.net' + $match.href } else { '' }"`) do (
   set "MEDIAINFO_URL=%%A"
)
for %%A in ("%MEDIAINFO_URL%") do set "MEDIAINFO_ZIP_NAME=%%~nxA"
set "MEDIAINFO_ZIP_PATH=%TEMP_DIR%\%MEDIAINFO_ZIP_NAME%"
set "MEDIAINFO_EXTRACT_DIR=%TEMP_DIR%\mediainfo_extract"
powershell -Command "Invoke-WebRequest -Uri '!MEDIAINFO_URL!' -OutFile '!MEDIAINFO_ZIP_PATH!'" %>>LOG%
powershell -Command "Expand-Archive -Path '!MEDIAINFO_ZIP_PATH!' -DestinationPath '!MEDIAINFO_EXTRACT_DIR!' -Force" %>>LOG%
for /r "!MEDIAINFO_EXTRACT_DIR!" %%F in (MediaInfo.exe) do (
    move /Y "%%F" "!TOOLS_DIR!\%%~nxF" >nul
)

rem === Step 9: Install SQLite CLI ===
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command ^
  "$url = 'https://sqlite.org/download.html'; ^
   $html = Invoke-WebRequest -Uri $url; ^
   $link = $html.Links | Where-Object { $_.href -match 'sqlite-tools-win-x64-\d+\.zip$' } | Select-Object -First 1; ^
   if ($link) { 'https://sqlite.org' + $link.href } else { '' }"`) do (
   set "SQLITE_URL=%%A"
)
for %%A in ("%SQLITE_URL%") do set "SQLITE_ZIP_NAME=%%~nxA"
set "SQLITE_ZIP_PATH=%TEMP_DIR%\%SQLITE_ZIP_NAME%"
set "SQLITE_EXTRACT_DIR=%TEMP_DIR%\sqlite_extract"
powershell -Command "Invoke-WebRequest -Uri '!SQLITE_URL!' -OutFile '!SQLITE_ZIP_PATH!'" %>>LOG%
powershell -Command "Expand-Archive -Path '!SQLITE_ZIP_PATH!' -DestinationPath '!SQLITE_EXTRACT_DIR!' -Force" %>>LOG%
for /r "!SQLITE_EXTRACT_DIR!" %%F in (sqlite3.exe) do (
    move /Y "%%F" "!TOOLS_DIR!\%%~nxF" >nul
)

rem === Final Cleanup ===
:cleanup
rmdir /s /q "%TEMP_DIR%" >nul 2>&1
if not "%QUIET%"=="1" (
    echo.
    echo ✅ UltimateMediaRenamer setup complete.
    pause
)
endlocal
