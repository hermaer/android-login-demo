@echo off
setlocal EnableExtensions
cd /d "%~dp0" || goto path_error
if not exist ".venv\Scripts\python.exe" goto setup_needed

echo Starting the application...
".venv\Scripts\python.exe" "src\main.py"
if errorlevel 1 goto run_error
exit /b 0

:path_error
echo ERROR: Cannot open the project folder. Unzip the project first.
goto fail
:setup_needed
echo ERROR: Dependencies are not installed. Run install_windows.bat first.
goto fail
:run_error
echo ERROR: The application stopped with an error. See the output above.
goto fail
:fail
pause
exit /b 1
