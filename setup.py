from setuptools import setup, find_packages

setup(
    name="cv_system",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "ultralytics>=8.0.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "filterpy>=1.4.5",
        "scipy>=1.10.0",
        "pyyaml>=6.0",
    ],
    author="CV System",
    description="Real-time object detection, tracking and counting system",
    python_requires=">=3.8",
)
