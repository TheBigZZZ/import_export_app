from setuptools import find_packages, setup

setup(
    name="tradedesk",
    version="0.0.1",
    packages=find_packages(include=["tradedesk", "tradedesk.*"]),
    include_package_data=True,
    install_requires=[
        "pydantic>=2.0",
    ],
)
