@echo off
setlocal

:: --- 1. Clean Environment (if any) ---
echo.
echo ===========================================
echo 1. Cleaning up previous build artifacts...
echo ===========================================

:: Remove previous virtual environment, build, and dist folders
if exist venv rmdir /s /q venv
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: --- 2. Create and Activate Virtual Environment ---
echo.
echo ===========================================
echo 2. Creating Python virtual environment...
echo ===========================================
py.exe -m venv venv

:: Activate the environment
call venv\Scripts\activate.bat

if not exist venv\Scripts\activate.bat (
echo.
echo ERROR: Virtual environment activation script not found.
echo Ensure 'py.exe' is available in your PATH.
goto :end
)

:: --- 3. Install Dependencies ---
echo.
echo ===========================================
echo 3. Installing MaxChat dependencies and PyInstaller...
echo ===========================================

:: Install PyInstaller and app dependencies
pip install pyinstaller
pip install -r requirements.txt

if errorlevel 1 (
echo.
echo ERROR: Failed to install dependencies. Check requirements.txt and network connection.
goto :end
)

:: --- 4. Build Executable ---
echo.
echo ===========================================
echo 4. Building MaxChat executable...
echo ===========================================
pyinstaller --onefile --windowed lan_chat.py

if errorlevel 1 (
echo.
echo ERROR: PyInstaller failed to build the executable.
goto :end
)

:: --- 5. Finish ---
echo.
echo ===========================================
echo Build Successful!
echo Executable is located at: dist\lan_chat.exe
echo ===========================================

:end
:: Deactivate the virtual environment
deactivate
echo.
pause
