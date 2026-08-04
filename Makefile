# SPDX-FileCopyrightText: 2011-2026 Sébastien Helleu <flashcode@flashtux.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

CONTAINER_CMD ?= "docker"

.PHONY: all check lint flake8 pylint container

all: check container

check: lint

lint: flake8 pylint bandit

flake8:
	flake8 . --count --select=E9,F63,F7,F82 --ignore=E203,W503 --show-source --statistics
	flake8 . --count --ignore=E203,W503 --exit-zero --max-complexity=10 --statistics

pylint:
	pylint weercd.py

bandit:
	bandit --skip B311 weercd.py

container:
	$(CONTAINER_CMD) build -f Containerfile -t weercd .
