#!/usr/bin/env python3
"""
代码格式化脚本
自动格式化和整理代码
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """运行命令并返回是否成功"""
    print(f"\n=== {description} ===")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} 完成")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败")
        print(e.stdout)
        print(e.stderr)
        return False


def main():
    """主函数"""
    print("🎨 开始代码格式化...")

    # 格式化步骤
    steps = [
        (["black", "."], "Black 代码格式化"),
        (["isort", "."], "导入排序整理"),
    ]

    failed_steps = []

    for cmd, description in steps:
        if not run_command(cmd, description):
            failed_steps.append(description)

    if failed_steps:
        print(f"\n❌ {len(failed_steps)} 个格式化步骤失败:")
        for step in failed_steps:
            print(f"  - {step}")
        sys.exit(1)

    print("\n🎉 代码格式化完成！")
    sys.exit(0)


if __name__ == "__main__":
    main()
