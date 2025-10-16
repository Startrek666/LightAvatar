#!/bin/bash
# Installation script for Lightweight Avatar Chat

set -e

echo "========================================"
echo "Lightweight Avatar Chat Installation"
echo "========================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "Error: Python $required_version or higher is required, but $python_version is installed."
    exit 1
fi
echo "✓ Python $python_version"

# Check Node.js
echo "Checking Node.js..."
if command -v node &> /dev/null; then
    node_version=$(node --version)
    echo "✓ Node.js $node_version"
else
    echo "✗ Node.js not found. Please install Node.js 18 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install backend dependencies
echo ""
echo "Installing backend dependencies..."
pip install -r requirements.txt

# Download Silero VAD model
echo ""
echo "Downloading Silero VAD model..."
python -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad', force_reload=False)" || true

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Install monitor dependencies
echo ""
echo "Installing monitor dependencies..."
cd monitor
npm install
cd ..

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p models logs static ssl_certs

# Download models
echo ""
echo "Downloading models..."
echo "This may take a while depending on your internet connection..."
python scripts/download_models.py

# Generate self-signed SSL certificate
echo ""
echo "Generating self-signed SSL certificate..."
openssl req -x509 -newkey rsa:4096 -keyout ssl_certs/key.pem -out ssl_certs/cert.pem -days 365 -nodes -subj "/CN=localhost"

# Build frontend
echo ""
echo "Building frontend..."
cd frontend
npm run build
cd ..

# Build monitor
echo ""
echo "Building monitor..."
cd monitor
npm run build
cd ..

echo ""
echo "========================================"
echo "Installation completed successfully!"
echo "========================================"
echo ""
echo "To start the application:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Start backend: python backend/app/main.py"
echo "  3. Access the application at: https://localhost:8000"
echo "  4. Access the monitor at: https://localhost:8000/monitor"
echo ""
echo "For development:"
echo "  - Backend: python backend/app/main.py"
echo "  - Frontend: cd frontend && npm run dev"
echo "  - Monitor: cd monitor && npm run dev"
echo ""
