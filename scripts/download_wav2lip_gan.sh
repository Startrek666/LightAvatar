#!/bin/bash
# Download Wav2Lip GAN model for better lip-sync quality

set -e

echo "====================================="
echo "Downloading Wav2Lip GAN Model"
echo "====================================="

MODEL_DIR="models/wav2lip"
MODEL_FILE="$MODEL_DIR/wav2lip_gan.pth"

# Create directory
mkdir -p "$MODEL_DIR"

# Check if already exists
if [ -f "$MODEL_FILE" ]; then
    echo "✓ Wav2Lip GAN model already exists: $MODEL_FILE"
    exit 0
fi

echo "Downloading Wav2Lip GAN model..."
echo "This will improve lip-sync quality significantly."
echo ""

# Try multiple sources
SUCCESS=false

# Source 1: Try gdown (Google Drive)
echo "Attempting to download from Google Drive using gdown..."
if command -v gdown &> /dev/null; then
    if gdown 15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk -O "$MODEL_FILE" 2>/dev/null; then
        SUCCESS=true
        echo "✓ Downloaded from Google Drive"
    fi
else
    echo "  gdown not found, trying pip install..."
    if pip install gdown &> /dev/null; then
        if gdown 15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk -O "$MODEL_FILE" 2>/dev/null; then
            SUCCESS=true
            echo "✓ Downloaded from Google Drive"
        fi
    fi
fi

# Source 2: Hugging Face (fallback)
if [ "$SUCCESS" = false ]; then
    echo "Trying Hugging Face mirror..."
    if wget -O "$MODEL_FILE" "https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth" 2>/dev/null; then
        SUCCESS=true
        echo "✓ Downloaded from Hugging Face"
    fi
fi

# Source 3: Manual download instruction
if [ "$SUCCESS" = false ]; then
    echo ""
    echo "====================================="
    echo "Automatic download failed!"
    echo "====================================="
    echo ""
    echo "Please download manually:"
    echo ""
    echo "1. Open in browser:"
    echo "   https://drive.google.com/file/d/15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk/view?usp=share_link"
    echo ""
    echo "2. Download the file (wav2lip_gan.pth, ~148MB)"
    echo ""
    echo "3. Upload to server:"
    echo "   scp wav2lip_gan.pth root@server:$MODEL_FILE"
    echo ""
    echo "Or try manually:"
    echo "   pip install gdown"
    echo "   gdown 15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk -O $MODEL_FILE"
    echo ""
    exit 1
fi

# Verify download
if [ -f "$MODEL_FILE" ]; then
    FILE_SIZE=$(stat -f%z "$MODEL_FILE" 2>/dev/null || stat -c%s "$MODEL_FILE" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -gt 100000000 ]; then  # > 100MB
        echo ""
        echo "====================================="
        echo "✓ Wav2Lip GAN model downloaded successfully!"
        echo "  Location: $MODEL_FILE"
        echo "  Size: $(($FILE_SIZE / 1024 / 1024)) MB"
        echo ""
        echo "The service will now use GAN model for enhanced quality."
        echo "Please restart the service: sudo systemctl restart lightavatar"
        echo "====================================="
    else
        echo "✗ Download failed or file is too small"
        rm -f "$MODEL_FILE"
        exit 1
    fi
else
    echo "✗ Download failed"
    exit 1
fi
