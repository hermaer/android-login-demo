@echo off
setlocal EnableExtensions
cd /d "%~dp0" || goto path_error

echo [1/3] Checking Python...
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv ".venv"
goto check_venv

:use_python
where python >nul 2>nul
if errorlevel 1 goto python_error
python -m venv ".venv"

:check_venv
if not exist ".venv\Scripts\python.exe" goto venv_error

:dependencies
echo [2/3] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_error

echo [3/3] Installing Flet 1.0.5 and secure storage...
".venv\Scripts\python.exe" -m pip install "flet[all]==1.0.5" "flet-secure-storage==1.0.5"
if errorlevel 1 goto install_error

echo.
echo SUCCESS: Setup finished. Run run_windows.bat next.
pause
exit /b 0

:path_error
echo ERROR: Cannot open the project folder. Unzip the project to a normal local directory.
goto fail
:python_error
echo ERROR: Python not found. Install 64-bit Python 3.10+ from python.org.
goto fail
:venv_error
echo ERROR: Virtual environment was not created. Check Python and permissions.
goto fail
:install_error
echo ERROR: Package installation failed. Check the output above and your internet connection.
goto fail
:fail
pause
exit /b 1
