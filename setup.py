from setuptools import setup
from package import Package

setup(
    name="ote_utils",
    version="1.1.2",
    description="collection of ote utils",
    packages=["ote_utils", "ote_utils.linux", "ote_utils.netconfutils", "ote_utils.utils"],
    cmdclass={"package": Package},
)
