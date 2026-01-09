"""
Pytest 配置文件

用于注册自定义命令行选项和共享 fixtures
"""


def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--no-log", action="store_true", default=False, help="禁用日志记录功能"
    )
