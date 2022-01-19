#
# Copyright (C) 2011-2022 Sébastien Helleu <flashcode@flashtux.org>
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

CONTAINER_CMD ?= "docker"

.PHONY: all check lint flake8 pylint container

all: check container

check: lint

lint: flake8 pylint bandit

flake8:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --statistics

pylint:
	pylint weercd.py

bandit:
	bandit --skip B311 weercd.py

container:
	$(CONTAINER_CMD) build -f Containerfile -t weercd .
