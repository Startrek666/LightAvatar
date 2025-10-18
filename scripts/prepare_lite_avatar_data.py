"""
LiteAvatar数据准备脚本
从lite-avatar-main项目复制所需的Avatar数据到lightweight-avatar-chat项目
"""
import argparse
import shutil
from pathlib import Path
from loguru import logger
import zipfile


def extract_sample_data(lite_avatar_path: Path, avatar_name: str = "default") -> Path:
    """
    解压sample_data.zip
    
    Args:
        lite_avatar_path: lite-avatar-main项目路径
        avatar_name: Avatar名称
    
    Returns:
        解压后的数据目录
    """
    zip_path = lite_avatar_path / "data" / "sample_data.zip"
    
    if not zip_path.exists():
        logger.error(f"找不到sample_data.zip: {zip_path}")
        logger.info("请从 https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery 下载")
        raise FileNotFoundError(str(zip_path))
    
    # 解压到临时目录
    extract_dir = lite_avatar_path / "data" / "extracted"
    extract_dir.mkdir(exist_ok=True, parents=True)
    
    logger.info(f"正在解压 {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # 查找解压后的数据目录
    extracted_dirs = list(extract_dir.glob("*"))
    if not extracted_dirs:
        raise RuntimeError("解压失败，未找到任何文件")
    
    data_dir = extracted_dirs[0]
    logger.info(f"数据已解压到: {data_dir}")
    
    return data_dir


def copy_avatar_data(source_dir: Path, target_dir: Path, avatar_name: str):
    """
    复制Avatar数据
    
    Args:
        source_dir: 源数据目录（lite-avatar-main中的数据）
        target_dir: 目标目录（lightweight-avatar-chat/models/lite_avatar/）
        avatar_name: Avatar名称
    """
    avatar_target = target_dir / avatar_name
    avatar_target.mkdir(exist_ok=True, parents=True)
    
    # 必需文件列表
    required_files = [
        "net_encode.pt",
        "net_decode.pt",
        "neutral_pose.npy",
        "bg_video.mp4",
        "face_box.txt"
    ]
    
    required_dirs = [
        "ref_frames"
    ]
    
    logger.info(f"正在复制Avatar数据到 {avatar_target}...")
    
    # 复制文件
    for filename in required_files:
        src = source_dir / filename
        dst = avatar_target / filename
        
        if not src.exists():
            logger.warning(f"警告: 找不到文件 {filename}")
            continue
        
        logger.info(f"  复制: {filename} ({src.stat().st_size / 1024 / 1024:.2f} MB)")
        shutil.copy2(src, dst)
    
    # 复制目录
    for dirname in required_dirs:
        src = source_dir / dirname
        dst = avatar_target / dirname
        
        if not src.exists():
            logger.warning(f"警告: 找不到目录 {dirname}")
            continue
        
        if dst.exists():
            shutil.rmtree(dst)
        
        logger.info(f"  复制目录: {dirname} ({len(list(src.glob('*')))} 个文件)")
        shutil.copytree(src, dst)
    
    logger.info(f"✓ Avatar数据已复制到: {avatar_target}")


def download_models(target_dir: Path, lite_avatar_path: Path = None):
    """
    下载LiteAvatar模型
    
    Args:
        target_dir: 目标目录
        lite_avatar_path: lite-avatar项目路径（可选）
    """
    model_path = target_dir / "model_1.onnx"
    
    if model_path.exists():
        logger.info(f"模型已存在: {model_path}")
        return
    
    logger.info("检查Audio2Mouth模型...")
    
    # 方案1: 从lite-avatar-main复制（如果已下载）
    if lite_avatar_path and lite_avatar_path.exists():
        source_model = lite_avatar_path / "weights" / "model_1.onnx"
        if source_model.exists():
            logger.info(f"从lite-avatar复制模型: {source_model}")
            shutil.copy2(source_model, model_path)
            logger.info("✓ 模型复制成功")
            return
    
    # 方案2: 使用modelscope CLI下载
    try:
        import subprocess
        logger.info("尝试使用modelscope CLI下载...")
        result = subprocess.run(
            [
                "modelscope", "download",
                "--model", "HumanAIGC-Engineering/LiteAvatarGallery",
                "lite_avatar_weights/model_1.onnx",
                "--local_dir", str(target_dir.parent)
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # 移动文件到正确位置
            downloaded = target_dir.parent / "lite_avatar_weights" / "model_1.onnx"
            if downloaded.exists():
                shutil.move(str(downloaded), str(model_path))
                # 清理
                shutil.rmtree(target_dir.parent / "lite_avatar_weights", ignore_errors=True)
                logger.info("✓ 模型下载成功")
                return
        else:
            logger.warning(f"modelscope下载失败: {result.stderr}")
    except FileNotFoundError:
        logger.warning("未安装modelscope CLI，跳过自动下载")
    except Exception as e:
        logger.warning(f"自动下载失败: {e}")
    
    # 方案3: 提示手动下载
    logger.info("=" * 60)
    logger.info("需要手动下载 model_1.onnx")
    logger.info("")
    logger.info("方案1: 使用官方脚本（推荐）")
    logger.info("  1. cd d:/Aprojects/Light-avatar/lite-avatar-main")
    logger.info("  2. 运行 download_model.bat (Windows) 或 bash download_model.sh (Linux)")
    logger.info("  3. 重新运行本脚本")
    logger.info("")
    logger.info("方案2: ModelScope手动下载")
    logger.info("  访问: https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatar/files")
    logger.info(f"  下载后放置到: {model_path}")
    logger.info("=" * 60)


def verify_data(avatar_dir: Path) -> bool:
    """
    验证Avatar数据完整性
    
    Args:
        avatar_dir: Avatar数据目录
    
    Returns:
        是否完整
    """
    required_files = [
        "net_encode.pt",
        "net_decode.pt",
        "neutral_pose.npy",
        "bg_video.mp4",
        "face_box.txt"
    ]
    
    required_dirs = [
        "ref_frames"
    ]
    
    logger.info("验证数据完整性...")
    
    all_ok = True
    for filename in required_files:
        filepath = avatar_dir / filename
        if not filepath.exists():
            logger.error(f"✗ 缺少文件: {filename}")
            all_ok = False
        else:
            size_mb = filepath.stat().st_size / 1024 / 1024
            logger.info(f"✓ {filename} ({size_mb:.2f} MB)")
    
    for dirname in required_dirs:
        dirpath = avatar_dir / dirname
        if not dirpath.exists():
            logger.error(f"✗ 缺少目录: {dirname}")
            all_ok = False
        else:
            file_count = len(list(dirpath.glob('*')))
            logger.info(f"✓ {dirname}/ ({file_count} 个文件)")
    
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="准备LiteAvatar数据")
    parser.add_argument(
        "--lite-avatar-path",
        type=str,
        default="d:/Aprojects/Light-avatar/lite-avatar-main",
        help="lite-avatar-main项目路径"
    )
    parser.add_argument(
        "--target-path",
        type=str,
        default="d:/Aprojects/Light-avatar/lightweight-avatar-chat",
        help="lightweight-avatar-chat项目路径"
    )
    parser.add_argument(
        "--avatar",
        type=str,
        default="default",
        help="Avatar名称"
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="跳过解压（如果已经解压过）"
    )
    
    args = parser.parse_args()
    
    lite_avatar_path = Path(args.lite_avatar_path)
    target_path = Path(args.target_path)
    
    if not lite_avatar_path.exists():
        logger.error(f"找不到lite-avatar-main项目: {lite_avatar_path}")
        return
    
    if not target_path.exists():
        logger.error(f"找不到lightweight-avatar-chat项目: {target_path}")
        return
    
    try:
        # 1. 解压sample_data（如果需要）
        if not args.skip_extract:
            data_dir = extract_sample_data(lite_avatar_path, args.avatar)
        else:
            # 使用已解压的数据
            data_dir = lite_avatar_path / "data" / "extracted"
            extracted_dirs = list(data_dir.glob("*"))
            if not extracted_dirs:
                logger.error("找不到已解压的数据，请不要使用--skip-extract")
                return
            data_dir = extracted_dirs[0]
        
        # 2. 复制Avatar数据
        target_model_dir = target_path / "models" / "lite_avatar"
        copy_avatar_data(data_dir, target_model_dir, args.avatar)
        
        # 3. 下载模型（如果需要）
        download_models(target_model_dir, lite_avatar_path)
        
        # 4. 验证数据
        avatar_dir = target_model_dir / args.avatar
        if verify_data(avatar_dir):
            logger.info("=" * 60)
            logger.info("✓ Avatar数据准备完成！")
            logger.info(f"  Avatar名称: {args.avatar}")
            logger.info(f"  数据目录: {avatar_dir}")
            logger.info("")
            logger.info("下一步:")
            logger.info("  1. 确保model_1.onnx已下载")
            logger.info("  2. 修改config/config.yaml，设置avatar.engine为'lite'")
            logger.info("  3. 重启服务")
        else:
            logger.error("✗ 数据不完整，请检查错误信息")
    
    except Exception as e:
        logger.error(f"准备失败: {e}")
        raise


if __name__ == "__main__":
    main()
