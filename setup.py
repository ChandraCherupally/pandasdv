from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="pandasdv",                     
    version="0.1.3",                             
    author="NaveenChandra Cherupally",
    author_email="cherupallynaveen@gmail.com",
    description="A simple survey data validation package using pandas.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ChandraCherupally/pandasdv",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.3.3",
        "numpy>=2.2.6",
        "pyreadstat==1.3.1"
    ],
    python_requires=">=3.8",
)
