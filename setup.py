"""Package metadata for installing the GeoRAG command-line client."""

from setuptools import find_packages, setup


setup(
    name="georag-cli",
    version="0.1.0",
    description="Agent-friendly command-line client for GeoRAG",
    packages=find_packages(include=["georag_cli", "georag_cli.*"]),
    install_requires=["httpx>=0.24.0", "keyring>=25.0.0"],
    entry_points={"console_scripts": ["georag=georag_cli.__main__:main"]},
)
