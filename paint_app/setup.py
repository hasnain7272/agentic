from setuptools import setup, find_packages

setup(
    name="agentcore-paint",
    version="1.0.0",
    description="A Paint-like application with A2A and Tools integration",
    author="AgentCore Swarm",
    packages=find_packages(),
    install_requires=[
        "Pillow>=10.0.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "agentcore-paint=main:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics :: Editors :: Raster-Based",
    ],
)