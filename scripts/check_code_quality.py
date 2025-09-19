#!/usr/bin/env python3
"""
代码质量检查脚本
运行各种代码检查工具确保代码质量
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """运行命令并返回是否成功"""
    print(f"\n=== {description} ===")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} 通过")
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
    root_dir = Path(__file__).parent
    python_files = list(root_dir.rglob("*.py"))

    if not python_files:
        print("❌ 未找到 Python 文件")
        sys.exit(1)

    print(f"🔍 找到 {len(python_files)} 个 Python 文件")

    # 检查步骤
    checks = [
        (["black", "--check", "--diff", "."], "Black 格式检查"),
        (["isort", "--check-only", "--diff", "."], "导入排序检查"),
        (["flake8", "."], "Flake8 代码风格检查"),
        (["mypy", "."], "MyPy 类型检查"),
        (["bandit", "-r", "."], "Bandit 安全检查"),
    ]

    failed_checks = []

    for cmd, description in checks:
        if not run_command(cmd, description):
            failed_checks.append(description)

    if failed_checks:
        print(f"\n❌ {len(failed_checks)} 个检查失败:")
        for check in failed_checks:
            print(f"  - {check}")
        print("\n💡 运行以下命令修复:")
        print("  black .          # 格式化代码")
        print("  isort .          # 排序导入")
        print("  # 然后手动修复其他问题")
        sys.exit(1)

    print("\n🎉 所有检查通过！代码质量良好")
    sys.exit(0)


if __name__ == "__main__":
    main()
