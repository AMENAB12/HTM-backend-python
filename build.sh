#!/bin/bash

# Build script for Render deployment
echo "=== Build Script Starting ==="
echo "Python version check:"
python --version
python3 --version 2>/dev/null || echo "python3 not found"
python3.12 --version 2>/dev/null || echo "python3.12 not found"

# Get Python version
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Detected Python version: $PYTHON_VERSION"

echo "=== Installing packages ==="
pip install --upgrade pip setuptools wheel

# Choose requirements file based on Python version
if [[ "$PYTHON_VERSION" == "3.13" ]]; then
    echo "Using Python 3.13 compatible requirements..."
    REQUIREMENTS_FILE="requirements-python313.txt"
else
    echo "Using standard requirements..."
    REQUIREMENTS_FILE="requirements.txt"
fi

echo "Installing from $REQUIREMENTS_FILE with binary-only packages to avoid compilation..."
pip install --only-binary=all -r $REQUIREMENTS_FILE

echo "=== Build Script Complete ===" 