# SPDX-FileCopyrightText: 2021-2025 Sébastien Helleu <flashcode@flashtux.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

FROM docker.io/library/python:3.9-alpine

MAINTAINER Sébastien Helleu <flashcode@flashtux.org>

COPY weercd.py .
CMD ["python", "weercd.py"]
