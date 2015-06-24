#!/usr/bin/python
# coding: utf-8
import os
from setuptools import setup

# mkdir -p /var/butterknife/pool

setup(
    name = "butterknife",
    version = "0.1.10",
    author = u"Lauri Võsandi",
    author_email = "lauri.vosandi@gmail.com",
    description = "Butterknife makes bare-metal Linux deployment dead-simple using the Linux Containers (LXC) and Btrfs filesystem.",
    license = "MIT",
    keywords = "btrfs falcon multicast http snapshot bare-metal lxc jinja2",
    url = "http://github.com/laurivosandi/butterknife",
    packages=[
        "butterknife",
        "butterknife.transport",
    ],
    long_description=open("README.rst").read(),
    install_requires=[
        "click",
        "falcon",
        "jinja2"
    ],
    scripts=[
        "misc/butterknife"
    ],
    include_package_data = True,
    package_data={
        "butterknife": ["butterknife/templates/*.html"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: Freely Distributable",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: System :: Recovery Tools",
        "Topic :: System :: Software Distribution"        
    ],
)

