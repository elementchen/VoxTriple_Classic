"""
自动根据 build/flash_args 生成用于出厂 0x0 烧录的全量合并 bin 文件。
自动解析 bootloader、partition-table、otadata 与主 app 的准确烧录偏移，杜绝人为填错导致引导失败。
"""
import os
import sys
import subprocess

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(script_dir, "build")
    flash_args_path = os.path.join(build_dir, "flash_args")

    if not os.path.exists(flash_args_path):
        print(f"Error: {flash_args_path} not found. Please run idf.py build first.")
        sys.exit(1)

    with open(flash_args_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    flash_params = lines[0].split()
    offset_file_pairs = []

    for line in lines[1:]:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            offset = parts[0]
            bin_rel_path = parts[1]
            bin_full_path = os.path.normpath(os.path.join(build_dir, bin_rel_path))
            offset_file_pairs.extend([offset, bin_full_path])

    version = "v1.0.19"
    if len(sys.argv) > 1:
        version = sys.argv[1]

    output_merged_bin = os.path.join(build_dir, f"esp32_bt_mic_merged_{version}.bin")

    cmd = [
        sys.executable, "-m", "esptool",
        "--chip", "esp32",
        "merge_bin",
        "-o", output_merged_bin
    ] + flash_params + offset_file_pairs

    print(f"Executing: {' '.join(cmd)}")
    ret = subprocess.run(cmd)
    if ret.returncode == 0:
        size = os.path.getsize(output_merged_bin)
        print(f"\n[SUCCESS] Generated: {output_merged_bin} ({size} bytes)")
    else:
        print("\n[ERROR] merge_bin failed")
        sys.exit(ret.returncode)

if __name__ == "__main__":
    main()
