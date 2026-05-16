from setuptools import setup, find_packages

setup(
    name="jarvis-tireq",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "jarvis=jarvis.cli:main",
        ]
    },
    install_requires=[
        "fastapi", "uvicorn", "chromadb",
        "edge-tts", "sounddevice", "numpy", "pygame",
    ],
)
