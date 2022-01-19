# Weercd

[![Build Status](https://github.com/weechat/weercd/workflows/CI/badge.svg)](https://github.com/weechat/weercd/actions?query=workflow%3A%22CI%22)

Weercd is the WeeChat IRC testing server.

It can be used with any IRC client (not only WeeChat).

In the "flood" mode, various IRC commands are sent in a short time (privmsg,
notice, join/quit, ..) to test client resistance and memory usage (to quickly
detect memory leaks, for example with client scripts).

## Install

Weercd requires Python ≥ 3.6.

It is **STRONGLY RECOMMENDED** to connect this server with a client in a test
environment:

- For WeeChat, a temporary home directory (see below).
- On a test machine, because CPU will be used a lot by client to display
  messages from Weercd.
- If possible locally (i.e. server and client on same machine), to speed up
  data exchange between server and client.

## Run with WeeChat

Open a terminal and run server:

```
python3 weercd.py
```

Open another terminal and run WeeChat with a temporary home directory:

```
weechat --temp-dir
```

Note: the option `--temp-dir` (or `-t`) has been added in WeeChat 2.4, so with
an older version you can do: `weechat --dir /tmp/weechat` (this directory is
not automatically removed on exit).

Optional: install script(s) in WeeChat (for example `/script install xxx`).

Add server and connect to it:

```
/server add weercd 127.0.0.1/7777
/connect weercd
```

Wait some months…

WeeChat still not crashed and does not use 200 TB of RAM ?
Yeah, it's stable! \o/

## Run in a container

You can also run Weercd in a container, using [Docker](https://www.docker.com/)
or [Podman](https://podman.io/).

To build the container:

```
make container
```

To run the container as a daemon:

```
docker run -p 7777:7777 -d weercd
```

## Copyright

Copyright © 2011-2022 [Sébastien Helleu](https://github.com/flashcode)

This file is part of Weercd, the WeeChat IRC testing server.

Weercd is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

Weercd is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Weercd.  If not, see <https://www.gnu.org/licenses/>.
