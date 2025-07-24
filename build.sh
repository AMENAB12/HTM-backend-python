#!/bin/bash

# Build script for Render deployment
echo "=== Build Script Starting ==="
echo "Python version check:"
python --version
python3 --version 2>/dev/null || echo "python3 not found"
python3.12 --version 2>/dev/null || echo "python3.12 not found"

echo "=== Installing packages ==="
pip install --upgrade pip setuptools wheel
echo "Installing with binary-only packages to avoid compilation..."
pip install --only-binary=all -r requirements.txt

echo "=== Build Script Complete ===" 