from setuptools import find_packages, setup

setup(
    name="ote_utils",
    version="1.3.1",
    description="collection of ote utils",
    packages=find_packages(),
    install_requires=[
        "exemel==0.2.2",
        "lxml==3.7.3",
        "paramiko==2.6.0",
        "pyshark==0.4.2.4",
        "pyyaml==3.12",
        "yinsolidated==1.0.1",
        "future==0.16.0",
        "ply==3.4",
    ],
    python_requires=">=3.6",
)
