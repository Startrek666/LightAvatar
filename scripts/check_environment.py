#!/usr/bin/env python3
"""
环境检查脚本 - 验证部署环境是否满足要求

用法:
    python scripts/check_environment.py
"""

import sys
import os
import subprocess
from pathlib import Path
import importlib

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓{Colors.ENDC} {text}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠{Colors.ENDC} {text}")

def print_error(text):
    print(f"{Colors.RED}✗{Colors.ENDC} {text}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ{Colors.ENDC} {text}")

def check_python_version():
    """检查Python版本"""
    print_header("1. Python版本检查")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_info(f"Python版本: {version_str}")
    
    if version.major == 3 and version.minor >= 11:
        print_success("Python版本满足要求 (>= 3.11)")
        return True
    else:
        print_error(f"Python版本过低，需要 >= 3.11，当前: {version_str}")
        return False

def check_system_commands():
    """检查系统命令"""
    print_header("2. 系统命令检查")
    
    commands = {
        'ffmpeg': 'FFmpeg (视频编码)',
        'git': 'Git (版本控制)',
        'node': 'Node.js (前端构建)',
        'npm': 'NPM (包管理)',
    }
    
    results = []
    for cmd, desc in commands.items():
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                # 提取版本号
                version = result.stdout.split('\n')[0]
                print_success(f"{desc}: {version}")
                results.append(True)
            else:
                print_error(f"{desc}: 未安装")
                results.append(False)
        except FileNotFoundError:
            print_error(f"{desc}: 未找到命令 '{cmd}'")
            results.append(False)
        except Exception as e:
            print_warning(f"{desc}: 检查失败 ({e})")
            results.append(False)
    
    return all(results)

def check_python_packages():
    """检查Python包"""
    print_header("3. Python依赖包检查")
    
    required_packages = {
        'fastapi': '0.115.5',
        'uvicorn': '0.32.0',
        'faster_whisper': '1.0.3',
        'edge_tts': '6.1.18',
        'onnxruntime': '1.19.2',
        'opencv-python-headless': '4.10.0',
        'librosa': '0.10.2',
        'openai': '1.52.0',
        'loguru': '0.7.2',
        'pydantic': '2.9.2',
    }
    
    results = []
    for package, expected_version in required_packages.items():
        try:
            # 转换包名（导入名可能不同）
            import_name = package.replace('-', '_')
            if import_name == 'opencv_python_headless':
                import_name = 'cv2'
            elif import_name == 'faster_whisper':
                import_name = 'faster_whisper'
            
            mod = importlib.import_module(import_name)
            
            # 获取版本
            version = getattr(mod, '__version__', 'unknown')
            
            print_success(f"{package}: {version}")
            results.append(True)
            
        except ImportError:
            print_error(f"{package}: 未安装")
            print_info(f"  运行: pip install {package}=={expected_version}")
            results.append(False)
        except Exception as e:
            print_warning(f"{package}: {e}")
            results.append(False)
    
    return all(results)

def check_project_structure():
    """检查项目结构"""
    print_header("4. 项目结构检查")
    
    required_dirs = [
        'backend',
        'backend/app',
        'backend/handlers',
        'backend/core',
        'frontend',
        'config',
        'models',
        'scripts',
        'docs',
    ]
    
    required_files = [
        'requirements.txt',
        'README.md',
        'config/config.yaml',
        'backend/app/main.py',
    ]
    
    results = []
    
    # 检查目录
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print_success(f"目录: {dir_path}")
            results.append(True)
        else:
            print_error(f"目录缺失: {dir_path}")
            results.append(False)
    
    # 检查文件
    for file_path in required_files:
        path = Path(file_path)
        if path.exists() and path.is_file():
            print_success(f"文件: {file_path}")
            results.append(True)
        else:
            print_error(f"文件缺失: {file_path}")
            results.append(False)
    
    return all(results)

def check_models():
    """检查模型文件"""
    print_header("5. 模型文件检查")
    
    models_dir = Path('models')
    
    # Whisper模型
    whisper_dir = models_dir / 'whisper'
    if whisper_dir.exists() and any(whisper_dir.iterdir()):
        print_success(f"Whisper模型目录存在")
        # 列出模型
        for item in whisper_dir.iterdir():
            if item.is_dir():
                print_info(f"  - {item.name}")
    else:
        print_warning("Whisper模型未下载")
        print_info("  运行: python scripts/download_models.sh")
    
    # Wav2Lip模型
    wav2lip_pth = models_dir / 'wav2lip' / 'wav2lip.pth'
    wav2lip_onnx = models_dir / 'wav2lip' / 'wav2lip.onnx'
    
    if wav2lip_pth.exists():
        size_mb = wav2lip_pth.stat().st_size / 1024 / 1024
        print_success(f"Wav2Lip PyTorch模型: {size_mb:.1f} MB")
    else:
        print_warning("Wav2Lip PyTorch模型未下载")
        print_info("  运行: bash scripts/download_models.sh")
    
    if wav2lip_onnx.exists():
        size_mb = wav2lip_onnx.stat().st_size / 1024 / 1024
        print_success(f"Wav2Lip ONNX模型: {size_mb:.1f} MB")
    else:
        print_warning("Wav2Lip ONNX模型不存在（可选）")
        print_info("  运行: python scripts/convert_wav2lip_to_onnx.py")
    
    # Avatar模板
    avatars_dir = models_dir / 'avatars'
    if avatars_dir.exists():
        avatar_files = list(avatars_dir.glob('*'))
        if avatar_files:
            print_success(f"Avatar模板: 找到 {len(avatar_files)} 个文件")
            for f in avatar_files[:3]:  # 只显示前3个
                print_info(f"  - {f.name}")
        else:
            print_warning("Avatar模板目录为空")
            print_info("  请添加数字人视频或图片到 models/avatars/")
    else:
        print_warning("Avatar模板目录不存在")
    
    return True  # 模型检查不影响整体结果

def check_configuration():
    """检查配置文件"""
    print_header("6. 配置文件检查")
    
    config_file = Path('config/config.yaml')
    
    if not config_file.exists():
        print_error("config.yaml 不存在")
        return False
    
    try:
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 检查关键配置
        if 'llm' in config:
            llm_config = config['llm']
            api_url = llm_config.get('api_url', '')
            api_key = llm_config.get('api_key', '')
            
            if api_url:
                print_success(f"LLM API地址: {api_url}")
            else:
                print_warning("LLM API地址未配置")
            
            if api_key:
                print_success("LLM API Key已配置")
            else:
                print_warning("LLM API Key未配置")
        else:
            print_warning("LLM配置缺失")
        
        # 检查其他配置
        sections = ['server', 'asr', 'tts', 'avatar', 'system']
        for section in sections:
            if section in config:
                print_success(f"配置段 [{section}] 存在")
            else:
                print_warning(f"配置段 [{section}] 缺失")
        
        return True
        
    except Exception as e:
        print_error(f"配置文件解析失败: {e}")
        return False

def check_ports():
    """检查端口占用"""
    print_header("7. 端口占用检查")
    
    ports = {
        8000: '后端API',
        80: 'Nginx/前端',
        3001: '监控面板',
    }
    
    try:
        import socket
        
        for port, desc in ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                print_warning(f"端口 {port} ({desc}) 已被占用")
            else:
                print_success(f"端口 {port} ({desc}) 可用")
        
    except Exception as e:
        print_warning(f"端口检查失败: {e}")
    
    return True

def main():
    """主函数"""
    print_header("Lightweight Avatar Chat 环境检查")
    
    # 检查是否在项目根目录
    if not Path('requirements.txt').exists():
        print_error("请在项目根目录运行此脚本")
        sys.exit(1)
    
    # 执行各项检查
    results = []
    
    results.append(("Python版本", check_python_version()))
    results.append(("系统命令", check_system_commands()))
    results.append(("Python包", check_python_packages()))
    results.append(("项目结构", check_project_structure()))
    results.append(("模型文件", check_models()))
    results.append(("配置文件", check_configuration()))
    results.append(("端口检查", check_ports()))
    
    # 总结
    print_header("检查总结")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    
    for name, result in results:
        if result:
            print_success(f"{name}: 通过")
        else:
            print_error(f"{name}: 失败")
    
    print()
    print(f"总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print_success("所有检查通过！环境已就绪")
        sys.exit(0)
    else:
        print_warning(f"有 {total - passed} 项检查未通过，请修复后重试")
        sys.exit(1)

if __name__ == '__main__':
    main()
