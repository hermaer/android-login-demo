@echo off
setlocal EnableExtensions
cd /d "%~dp0" || goto path_error
if not exist ".venv\Scripts\flet.exe" goto setup_needed

if exist "signing.local.bat" (
    call "signing.local.bat"
    if errorlevel 1 goto signing_error
) else (
    echo WARNING: signing.local.bat not found.
    echo APK may be signed with a temporary debug key.
    echo Stable signing is required for future in-place updates.
    echo See README.md before publishing releases.
    echo.
)

echo Building Android APK...
".venv\Scripts\flet.exe" build apk
if errorlevel 1 goto build_error

echo.
echo SUCCESS: Check the build\apk folder for the APK file.
pause
exit /b 0

:path_error
echo ERROR: Cannot open the project folder. Unzip the project first.
goto fail
:setup_needed
echo ERROR: Flet is not installed. Run install_windows.bat first.
goto fail
:signing_error
echo ERROR: Your signing configuration returned an error.
goto fail
:build_error
echo ERROR: Android APK build failed. See the output above.
goto fail
:fail
pause
exit /b 1
