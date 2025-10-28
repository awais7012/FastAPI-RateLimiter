"""
FastAPI Rate Limiter - Setup Configuration
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="fastapi-advanced-rate-limiter",
    version="2.0.0",
    description="High-performance, multi-algorithm rate limiting for FastAPI with Redis and in-memory backends",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ahmed Awais (Romeo)",
    author_email="ahmadawaisgithub@gmail.com",
    url="https://github.com/awais7012/FastAPI-RateLimiter",
    project_urls={
        "Bug Tracker": "https://github.com/awais7012/FastAPI-RateLimiter/issues",
        "Documentation": "https://github.com/awais7012/FastAPI-RateLimiter#readme",
        "Source Code": "https://github.com/awais7012/FastAPI-RateLimiter",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=[
        "fastapi",
        "rate-limiter",
        "rate-limiting",
        "throttling",
        "api",
        "redis",
        "token-bucket",
        "leaky-bucket",
        "sliding-window",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.68.0",
    ],
    extras_require={
        "redis": ["redis>=4.0.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "all": [
            "redis>=4.0.0",
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)