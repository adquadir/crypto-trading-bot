from setuptools import setup, find_packages

setup(
    name="crypto-trading-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "python-binance",
        "pandas",
        "numpy",
        "sqlalchemy",
        "python-dotenv",
        "websockets",
        "aiohttp",
        "ccxt",
    ],
    python_requires=">=3.8",
) 