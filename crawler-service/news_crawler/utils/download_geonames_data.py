#!/usr/bin/env python3
"""
GeoNames 原始数据下载脚本

从 GeoNames (https://download.geonames.org/export/dump/) 下载构建地理词典所需的原始数据文件。

数据源许可证: Creative Commons Attribution 4.0 License
"""

import os
import sys
import zipfile
import logging
import urllib.request

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GeoNames 下载基础 URL
GEONAMES_BASE_URL = "https://download.geonames.org/export/dump"

# 需要下载的文件列表
GEONAMES_FILES = {
    "countryInfo.txt": {
        "url": f"{GEONAMES_BASE_URL}/countryInfo.txt",
        "description": "国家基础信息（ISO代码、名称、首都、人口等）",
        "compressed": False,
    },
    "admin1CodesASCII.txt": {
        "url": f"{GEONAMES_BASE_URL}/admin1CodesASCII.txt",
        "description": "一级行政区编码与名称",
        "compressed": False,
    },
    "cities15000.zip": {
        "url": f"{GEONAMES_BASE_URL}/cities15000.zip",
        "description": "人口>15000的全球城市",
        "compressed": True,
        "extract_file": "cities15000.txt",
    },
    "alternateNamesV2.zip": {
        "url": f"{GEONAMES_BASE_URL}/alternateNamesV2.zip",
        "description": "多语言地名别名（含中文）",
        "compressed": True,
        "extract_file": "alternateNamesV2.txt",
    },
}

# 输出目录
RAW_DIR = os.path.join(os.path.dirname(__file__), "geo_dictionaries", "raw")


def ensure_raw_dir():
    """确保 raw/ 目录存在"""
    os.makedirs(RAW_DIR, exist_ok=True)
    logger.info(f"原始数据目录: {RAW_DIR}")


def download_file(url: str, dest_path: str, description: str) -> bool:
    """下载单个文件"""
    if os.path.exists(dest_path):
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        logger.info(f"文件已存在，跳过下载: {os.path.basename(dest_path)} ({size_mb:.1f}MB)")
        return True

    logger.info(f"正在下载: {description}")
    logger.info(f"  URL: {url}")
    logger.info(f"  目标: {dest_path}")

    try:
        urllib.request.urlretrieve(url, dest_path, reporthook=_download_progress)
        print()  # 换行
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        logger.info(f"下载完成: {os.path.basename(dest_path)} ({size_mb:.1f}MB)")
        return True
    except Exception as e:
        logger.error(f"下载失败: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def _download_progress(block_num, block_size, total_size):
    """下载进度回调"""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, downloaded * 100 / total_size)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        sys.stdout.write(f"\r  进度: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)")
        sys.stdout.flush()


def extract_zip(zip_path: str, extract_file: str) -> bool:
    """从 zip 文件中提取指定文件"""
    extract_path = os.path.join(RAW_DIR, extract_file)

    if os.path.exists(extract_path):
        size_mb = os.path.getsize(extract_path) / (1024 * 1024)
        logger.info(f"已解压文件存在，跳过: {extract_file} ({size_mb:.1f}MB)")
        return True

    logger.info(f"正在解压: {extract_file} 从 {os.path.basename(zip_path)}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extract(extract_file, RAW_DIR)
        size_mb = os.path.getsize(extract_path) / (1024 * 1024)
        logger.info(f"解压完成: {extract_file} ({size_mb:.1f}MB)")
        return True
    except Exception as e:
        logger.error(f"解压失败: {e}")
        return False


def download_all():
    """下载所有需要的 GeoNames 数据文件"""
    ensure_raw_dir()

    success_count = 0
    fail_count = 0

    for filename, config in GEONAMES_FILES.items():
        dest_path = os.path.join(RAW_DIR, filename)
        ok = download_file(config["url"], dest_path, config["description"])

        if ok and config.get("compressed"):
            extract_file = config["extract_file"]
            ok = extract_zip(dest_path, extract_file)

        if ok:
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"\n下载完成: 成功 {success_count}/{len(GEONAMES_FILES)}，失败 {fail_count}")

    if fail_count > 0:
        logger.warning("部分文件下载失败，请检查网络连接后重试")
        return False

    # 列出 raw/ 目录下所有文件
    logger.info("\nraw/ 目录内容:")
    for f in sorted(os.listdir(RAW_DIR)):
        fpath = os.path.join(RAW_DIR, f)
        if os.path.isfile(fpath):
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            logger.info(f"  {f}: {size_mb:.1f}MB")

    return True


def check_raw_files() -> dict:
    """检查 raw/ 目录下已有的原始数据文件"""
    status = {}
    for filename, config in GEONAMES_FILES.items():
        if config.get("compressed"):
            # 检查解压后的文件
            check_file = config["extract_file"]
        else:
            check_file = filename

        fpath = os.path.join(RAW_DIR, check_file)
        exists = os.path.exists(fpath)
        size = os.path.getsize(fpath) if exists else 0

        status[check_file] = {
            "exists": exists,
            "size_bytes": size,
            "description": config["description"],
        }

    return status


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="下载 GeoNames 原始数据文件")
    parser.add_argument("--check", action="store_true", help="仅检查文件状态，不下载")
    args = parser.parse_args()

    if args.check:
        logger.info("检查原始数据文件状态...")
        status = check_raw_files()
        for fname, info in status.items():
            icon = "✅" if info["exists"] else "❌"
            size_mb = info["size_bytes"] / (1024 * 1024)
            logger.info(f"  {icon} {fname}: {'存在' if info['exists'] else '缺失'} ({size_mb:.1f}MB) - {info['description']}")
    else:
        download_all()
