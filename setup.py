from setuptools import find_packages
from setuptools import setup

with open("requirements.txt") as f:
    content = f.readlines()
requirements = [x.strip() for x in content if "git+" not in x and not x.strip().startswith("#") and x.strip()]

setup(
    name="respirasp",
    version="1.0.0",
    description="Respira SP — PM2.5 forecasting for São Paulo using LightGBM",
    license="MIT",
    author="MA4RKZ",
    install_requires=requirements,
    packages=find_packages(),
    test_suite="tests",
    include_package_data=True,
    zip_safe=False
)
