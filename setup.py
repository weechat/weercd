#!/usr/bin/env python3
#
# Copyright (C) 2011-2025 Sébastien Helleu <flashcode@flashtux.org>
#
# This file is part of Weercd, the WeeChat IRC testing server.
#
# Weercd is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Weercd is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Weercd.  If not, see <https://www.gnu.org/licenses/>.
#

from codecs import open
from setuptools import setup

DESCRIPTION = 'WeeChat IRC testing server.'

with open('README.md', 'r', 'utf-8') as f:
    readme = f.read()

setup(
    name='weercd',
    version='1.0.0-dev',
    description=DESCRIPTION,
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Sébastien Helleu',
    author_email='flashcode@flashtux.org',
    url='https://github.com/weechat/weercd',
    license='GPL3',
    keywords='irc server fuzzing',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 '
        'or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Communications :: Chat :: Internet Relay Chat',
    ],
    packages=['.'],
    entry_points={
        'console_scripts': ['weercd=weercd:main'],
    }
)
