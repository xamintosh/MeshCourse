#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# --- 1. Clean Environment (if any) ---
echo "==========================================="
echo "1. Cleaning up previous build artifacts..."
echo "==========================================="

# Remove previous virtual environment, build, and dist folders
rm -rf venv build dist

# --- 2. Create and Activate Virtual Environment ---
echo
echo "==========================================="
echo "2. Creating Python virtual environment (using virtualenv)..."
echo "==========================================="

# Check if virtualenv is installed, install if not available
if ! command -v virtualenv &> /dev/null
then
    echo "virtualenv command not found. Attempting to install via pip..."
    # Attempt to install globally via pip
    pip install virtualenv || { echo "FATAL ERROR: Failed to install virtualenv. Please install it manually: 'pip install virtualenv'"; exit 1; }
fi

# Create the virtual environment
virtualenv venv

# Activate the environment
. venv/bin/activate

if [ ! -f "venv/bin/activate" ]; then
    echo
    echo "ERROR: Virtual environment activation script not found."
    echo "Please ensure 'virtualenv' is installed and functioning correctly."
    exit 1
fi

# --- 3. Install Dependencies ---
echo
echo "==========================================="
echo "3. Installing MaxChat dependencies and PyInstaller..."
echo "==========================================="

# PyInstaller is now included in requirements.txt
pip install -r requirements.txt

# --- 4. Build Executable ---
echo
echo "==========================================="
echo "4. Building MaxChat executable (Linux onefile)..."
echo "==========================================="
# Using --noconsole for a standalone GUI application
pyinstaller --onefile --noconsole lan_chat.py

# --- 5. Finish ---
echo
echo "==========================================="
echo "Build Successful!"
echo "Executable is located at: dist/lan_chat"
echo "==========================================="

# Deactivate the virtual environment
deactivate

echo
read -r -p "Press [Enter] to exit..."

