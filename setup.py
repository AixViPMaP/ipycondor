#!/usr/bin/env python
# -*- coding: utf-8
from sys import version_info

from io import open
from setuptools import setup, find_packages

setup(
    name='ipycondor',
    version='0.0.4',
    description='IPython binding for HTCondor',
    author='Mingxuan Lin, Lukas Koschmieder',
    license='GPL',
    packages=['ipycondor'],
    requires=['pandas', 'qgrid'],
    url='https://github.com/gdlmx/ipycondor',
    use_2to3=False,
    include_package_data=True,
    classifiers=[
        'Intended Audience :: End Users',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities'],
    keywords=['HTCondor', 'IPython']
)
