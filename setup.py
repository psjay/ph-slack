#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

install_requires = [
    "flask",
    "phabricator",
    "slacker",
]

entry_points = """
[console_scripts]
"""

setup(
    name="ph-slack",
    version="0.0.1",
    url='https://github.com/psjay/ph-slack',
    license='MIT',
    description="Slack Phabricator Notification integration.",
    author='psjay.peng@gmail.com',
    packages=find_packages(),
    install_requires=install_requires,
    entry_points=entry_points,
)
