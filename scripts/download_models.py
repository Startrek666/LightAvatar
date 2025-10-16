#!/usr/bin/env python3
"""
Download required models for the Lightweight Avatar Chat system
"""
import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm
import hashlib
import zipfile
import tarfile

# Model configurations
MODELS = {
    "whisper": {
        "small": {
            "url": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt",
            "sha256": "9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794",
            "size": "461MB"
        },
        "base": {
            "url": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
            "sha256": "ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e",
            "size": "139MB"
        },
        "tiny": {
            "url": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
            "sha256": "65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9",
            "size": "37.8MB"
        }
    },
    "wav2lip": {
        "model": {
            "url": "https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth",
            "sha256": None,
            "size": "435MB"
        }
    },
    "face_detection": {
        "model": {
            "url": "https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/s3fd.pth",
            "sha256": None,
            "size": "85MB"
        }
    }
}


def download_file(url: str, dest_path: Path, chunk_size: int = 8192) -> bool:
    """Download a file with progress bar"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(dest_path, 'wb') as f:
            with tqdm(
                desc=dest_path.name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    size = f.write(chunk)
                    pbar.update(size)
        
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Verify file SHA256 checksum"""
    if not expected_sha256:
        return True
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    actual_sha256 = sha256_hash.hexdigest()
    return actual_sha256 == expected_sha256


def extract_archive(archive_path: Path, extract_to: Path):
    """Extract archive file"""
    if archive_path.suffix == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.suffix in ['.tar', '.gz', '.bz2']:
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            tar_ref.extractall(extract_to)


def download_models(models_dir: Path, model_type: str = None):
    """Download specified models"""
    models_dir.mkdir(parents=True, exist_ok=True)
    
    if model_type:
        if model_type not in MODELS:
            print(f"Unknown model type: {model_type}")
            print(f"Available types: {', '.join(MODELS.keys())}")
            return
        
        models_to_download = {model_type: MODELS[model_type]}
    else:
        models_to_download = MODELS
    
    for category, models in models_to_download.items():
        category_dir = models_dir / category
        category_dir.mkdir(exist_ok=True)
        
        print(f"\nDownloading {category} models...")
        
        for model_name, model_info in models.items():
            model_path = category_dir / f"{model_name}.pt"
            if category == "wav2lip":
                model_path = category_dir / "wav2lip_gan.pth"
            elif category == "face_detection":
                model_path = category_dir / "s3fd.pth"
            
            # Check if already exists
            if model_path.exists():
                print(f"{model_name} already exists, skipping...")
                continue
            
            print(f"\nDownloading {model_name} ({model_info['size']})...")
            
            # Download
            if download_file(model_info['url'], model_path):
                # Verify checksum
                if model_info['sha256']:
                    if verify_sha256(model_path, model_info['sha256']):
                        print(f"✓ {model_name} downloaded and verified successfully")
                    else:
                        print(f"✗ {model_name} checksum verification failed!")
                        model_path.unlink()
                else:
                    print(f"✓ {model_name} downloaded successfully")
            else:
                print(f"✗ Failed to download {model_name}")


def convert_to_onnx():
    """Convert PyTorch models to ONNX format"""
    print("\nConverting models to ONNX format...")
    
    # This is a placeholder - actual conversion requires the model architecture
    print("Note: Model conversion to ONNX requires the original model architecture.")
    print("Please run scripts/convert_to_onnx.py after downloading the models.")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download models for Lightweight Avatar Chat")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("models"),
        help="Directory to save models (default: models)"
    )
    parser.add_argument(
        "--type",
        choices=list(MODELS.keys()),
        help="Download only specific model type"
    )
    parser.add_argument(
        "--convert-onnx",
        action="store_true",
        help="Convert models to ONNX format after downloading"
    )
    
    args = parser.parse_args()
    
    print("Lightweight Avatar Chat - Model Downloader")
    print("=" * 50)
    
    # Download models
    download_models(args.models_dir, args.type)
    
    # Convert to ONNX if requested
    if args.convert_onnx:
        convert_to_onnx()
    
    print("\nDone!")


if __name__ == "__main__":
    main()
