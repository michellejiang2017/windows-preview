@echo off
setlocal
cd /d "%~dp0"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%BUNDLED_PYTHON%" goto check_venv
if not exist "..\..\work\runtime\PySide6" goto check_venv
set "PYTHONPATH=%~dp0..\..\work\runtime"
set "U2NET_HOME=%~dp0..\..\work\models"
set "QT_QPA_PLATFORM=windows"
"%BUNDLED_PYTHON%" app.py %*
goto finish

:check_venv
if exist ".venv\Scripts\python.exe" goto dependencies
if exist "%BUNDLED_PYTHON%" goto bundled_venv
call py -3.12 -c "import sys; assert sys.version_info[:2] == (3,12)" >nul 2>nul
if errorlevel 1 goto missing_python
call py -3.12 -m venv .venv
if errorlevel 1 goto venv_failed
goto dependencies

:bundled_venv
"%BUNDLED_PYTHON%" -m venv .venv
if errorlevel 1 goto venv_failed

:dependencies
if not exist ".venv\Scripts\python.exe" goto venv_failed
fc /b requirements.txt ".venv\installed-requirements.txt" >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Python is available, but library installation failed. See the error above.
    pause
    exit /b 1
  )
  copy /y requirements.txt ".venv\installed-requirements.txt" >nul
)
".venv\Scripts\python.exe" app.py %*
:finish
if errorlevel 1 pause
exit /b

:missing_python
echo Python 3.12 is missing. This is a runtime setup issue.
echo Run: py install 3.12
echo Or install Python 3.12 from https://www.python.org/downloads/windows/
echo Then run this launcher again.
pause
exit /b 1

:venv_failed
echo Could not create the Python environment. Check that this folder is writable.
pause
exit /b 1
