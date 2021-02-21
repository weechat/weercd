FROM docker.io/library/python:3.9-alpine

MAINTAINER Sébastien Helleu <flashcode@flashtux.org>

COPY weercd.py .
CMD ["python", "weercd.py"]
