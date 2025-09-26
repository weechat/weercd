#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2011-2025 Sébastien Helleu <flashcode@flashtux.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
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

"""WeeChat IRC testing server."""

import argparse
import os
import random
import re
import select
import shlex
import signal
import socket
import string
import sys
import time
import traceback

from contextlib import contextmanager

NAME = "weercd"
VERSION = "1.0.0-dev"


class TimeoutException(Exception):
    pass


@contextmanager
def time_limit(seconds):
    """Set a time limit for a function."""
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    if seconds > 0:
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
    try:
        yield
    finally:
        if seconds > 0:
            signal.alarm(0)


def random_string(max_length, spaces=False):
    """Return a random string (random length and content)."""
    length = random.randint(1, max_length)
    chars = (
        string.ascii_uppercase
        + string.ascii_lowercase
        + string.digits
        + (" " if spaces else "")
    )
    return "".join(random.choice(chars) for x in range(length))


def random_host():
    """Return a random host name."""
    return f"{random_string(10)}@{random_string(10)}"


def random_channel():
    """Return a random channel name."""
    return f"#{random_string(25)}"


class Connection:  # pylint: disable=too-many-instance-attributes
    """Connection with a client."""

    def __init__(self, sock, addr, debug):
        self.sock = sock
        self.addr = addr
        self.debug = debug
        self.last_buffer = ""
        self.start_time = time.time()
        self.in_count = 0
        self.out_count = 0
        self.in_bytes = 0
        self.out_bytes = 0

    def __str__(self):
        """Return connection statistics."""
        elapsed = time.time() - self.start_time
        countrate = self.out_count / elapsed
        bytesrate = self.out_bytes / elapsed
        return (
            f"Elapsed: {elapsed:.1f}s - "
            f"packets: in:{self.in_count}, out:{self.out_count} "
            f"({countrate:.0f}/s) - "
            f"bytes: in:{self.in_bytes}, out: {self.out_bytes} "
            f"({bytesrate:.0f}/s)"
        )

    def read(self, timeout):
        """Read raw data received from client."""
        msgs = []
        inr = select.select([self.sock], [], [], timeout)[0]
        if inr:
            data = self.sock.recv(4096)
            if data:
                data = data.decode("UTF-8")
                self.in_bytes += len(data)
                data = self.last_buffer + data
                while True:
                    pos = data.find("\r\n")
                    if pos < 0:
                        break
                    msgs.append(data[0:pos])
                    data = data[pos + 2 :]
                self.last_buffer = data
        return msgs

    def send(self, data):
        """Send one message to client."""
        if self.debug:
            print(f"<-- {data}")
        msg = data + "\r\n"
        self.out_bytes += len(msg)
        self.sock.send(msg.encode("UTF-8"))
        self.out_count += 1

    def close(self):
        """Close connection with client."""
        print(f"Closing connection with {self.addr}")
        self.sock.close()


class Client:  # pylint: disable=too-many-instance-attributes
    """A client of Weercd server."""

    def __init__(self, sock, addr, args):
        self.conn = Connection(sock, addr, args.debug)
        self.name = NAME
        self.version = VERSION
        self.args = args
        self.nick = ""
        self.nick_number = 0
        self.channels = {}
        self.quit = False
        self.read_error = False
        self.end_msg = ""
        self.end_exception = None
        self.connect()

    def has_ended(self):
        """Check if the server has ended or the client has disconnected."""
        return self.quit or self.read_error

    def random_nick(self, with_number=False):
        """Return a random nick name."""
        if with_number:
            self.nick_number += 1
            return f"{random_string(5)}{self.nick_number}"
        return random_string(10)

    def random_channel_nick(self, channel):
        """Return a random nick of a channel."""
        if len(self.channels[channel]) < 2:
            return None
        rand_nick = self.nick
        while rand_nick == self.nick:
            rand_nick = self.channels[channel][
                random.randint(0, len(self.channels[channel]) - 1)
            ]
        return rand_nick

    def send(self, message):
        """Send an IRC message to the client."""
        self.conn.send(message)

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def send_command(self, command, data, nick=None, host="", target=None):
        """Send an IRC command to the client."""
        if nick is None:
            nick = self.name
        if target is None:
            target = self.nick
        sender = f':{nick}{"!" if host else ""}{host}'
        target = f'{" " if target else ""}{target}'
        data = f'{" :" if data else ""}{data}'
        self.send(f"{sender} {command}{target}{data}")

    def parse_message(self, message):
        """Read one IRC message from client."""
        if self.args.debug:
            print(f"--> {message}")
        if message.startswith("PING "):
            args = message[5:]
            if args[0] == ":":
                args = args[1:]
            self.send(f"PONG :{args}")
        elif message.startswith("NICK "):
            self.nick = message[5:]
        elif message.startswith("PART "):
            match = re.search("^PART :?(#[^ ]+)", message)
            if match:
                channel = match.group(1)
                if channel in self.channels:
                    del self.channels[channel]
        elif message.startswith("QUIT "):
            self.quit = True
        self.conn.in_count += 1

    def recv(self, timeout):
        """Receive messages and parse them."""
        try:
            msgs = self.conn.read(timeout)
        except Exception as exc:
            print(f"Error reading on socket: {exc}")
            self.read_error = True
            return
        for msg in msgs:
            self.parse_message(msg)

    def connect(self):
        """Inform the client that the connection is OK."""
        count = self.args.nickused
        while self.nick == "":
            self.recv(0.1)
            if self.has_ended():
                return
            if self.nick and count > 0:
                self.send_command(
                    "433",
                    "Nickname is already in use.",
                    target=f"* {self.nick}",
                )
                self.nick = ""
                count -= 1
        self.send_command("001", "Welcome to the WeeChat IRC server")
        self.send_command(
            "002",
            f"Your host is {self.name}, " f"running version {self.version}",
        )
        self.send_command("003", "Are you solid like a rock?")
        self.send_command("004", "Let's see!")

    def flood_self_join(self):
        """Self join on a new channel."""
        channel = random_channel()
        if channel in self.channels:
            return
        self.send_command(
            "JOIN", channel, nick=self.nick, host=self.conn.addr[0], target=""
        )
        self.send_command(
            "353", f"@{self.nick}", target=f"{self.nick} = {channel}"
        )
        self.send_command(
            "366", "End of /NAMES list.", target=f"{self.nick} {channel}"
        )
        self.channels[channel] = [self.nick]

    def flood_user_notice(self):
        """Notice for the user."""
        self.send_command(
            "NOTICE",
            random_string(400, spaces=True),
            nick=self.random_nick(),
            host=random_host(),
        )

    def flood_channel_join(self, channel):
        """Join of a user in a channel."""
        if len(self.channels[channel]) >= self.args.maxnicks:
            return
        newnick = self.random_nick(with_number=True)
        self.send_command(
            "JOIN", channel, nick=newnick, host=random_host(), target=""
        )
        self.channels[channel].append(newnick)

    def flood_channel_part(self, channel):
        """Part or quit of a user in a channel."""
        if not self.channels[channel]:
            return
        rand_nick = self.random_channel_nick(channel)
        if not rand_nick:
            return
        if random.randint(1, 2) == 1:
            self.send_command(
                "PART", channel, nick=rand_nick, host=random_host(), target=""
            )
        else:
            self.send_command(
                "QUIT",
                random_string(30),
                nick=rand_nick,
                host=random_host(),
                target="",
            )
        self.channels[channel].remove(rand_nick)

    def flood_channel_kick(self, channel):
        """Kick of a user in a channel."""
        if not self.channels[channel]:
            return
        rand_nick1 = self.random_channel_nick(channel)
        rand_nick2 = self.random_channel_nick(channel)
        if rand_nick1 and rand_nick2 and rand_nick1 != rand_nick2:
            self.send_command(
                "KICK",
                random_string(50),
                nick=rand_nick1,
                host=random_host(),
                target=f"{channel} {rand_nick2}",
            )
            self.channels[channel].remove(rand_nick2)

    def flood_channel_message(self, channel):
        """Message from a user in a channel."""
        if not self.channels[channel]:
            return
        rand_nick = self.random_channel_nick(channel)
        if not rand_nick:
            return
        msg = random_string(400, spaces=True)
        if "channel" in self.args.notice and random.randint(1, 100) == 100:
            # notice for channel
            self.send_command(
                "NOTICE",
                msg,
                nick=rand_nick,
                host=random_host(),
                target=channel,
            )
        else:
            # add random highlight
            if random.randint(1, 100) == 100:
                msg = f"{self.nick}: {msg}"
            action2 = random.randint(1, 50)
            if action2 == 1:
                # CTCP action (/me)
                msg = f"\x01ACTION {msg}\x01"
            elif action2 == 2:
                # CTCP version
                msg = "\x01VERSION\x01"
            self.send_command(
                "PRIVMSG",
                msg,
                nick=rand_nick,
                host=random_host(),
                target=channel,
            )

    def flood(self):
        """Yeah, funny stuff here! Flood the client!"""
        self.recv(self.args.sleep)
        # global actions
        action = random.randint(1, 2)
        if action == 1 and len(self.channels) < self.args.maxchans:
            self.flood_self_join()
        elif action == 2 and "user" in self.args.notice:
            self.flood_user_notice()
        # actions for each channel
        for channel in self.channels:
            action = random.randint(1, 50)
            if 1 <= action <= 10:
                self.flood_channel_join(channel)
            elif action == 11:
                self.flood_channel_part(channel)
            elif action == 12:
                self.flood_channel_kick(channel)
            else:
                self.flood_channel_message(channel)
        # display progress
        if self.conn.out_count % 1000 == 0:
            sys.stdout.write(".")
            sys.stdout.flush()

    def send_file(self):  # pylint: disable=too-many-branches
        """Send messages from a file to client."""
        stdin = self.args.file == sys.stdin
        count = 0
        self.recv(0.2)
        try:  # pylint: disable=too-many-nested-blocks
            while True:
                # display the prompt if we are reading in stdin
                if stdin:
                    sys.stdout.write("Message to send to client: ")
                    sys.stdout.flush()
                message = self.args.file.readline()
                if not message:
                    break
                message = message.rstrip("\n")
                if message:
                    if message.startswith("/") and message[1:2] != "/":
                        pass
                    elif not message.startswith("//"):
                        self.send(message.format(self=self))
                        count += 1
                self.recv(0.1 if stdin else self.args.sleep)
        except IOError as exc:
            self.end_msg = f"unable to read file {self.args.file}"
            self.end_exception = exc
            return
        except KeyboardInterrupt:
            self.end_msg = "interrupted"
            return
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc()
            self.end_msg = "connection lost"
            return
        finally:
            sys.stdout.write("\n")
            sys.stdout.write(
                f"{count} messages sent "
                f'from {"stdin" if stdin else "file"}, '
                f"press Enter to exit"
            )
            sys.stdout.flush()
            try:
                sys.stdin.readline()
            except KeyboardInterrupt:
                print("interrupted")

    def run(self):
        """Execute the action asked for the client."""
        if self.has_ended():
            return

        # send commands from file (which can be stdin)
        if self.args.file:
            self.send_file()
            return

        # wait a bit
        if self.args.wait > 0:
            print(f"Waiting {self.args.wait} seconds")
            time.sleep(self.args.wait)

        # flood the client
        sys.stdout.write("Flooding client..")
        sys.stdout.flush()
        with time_limit(self.args.time):
            try:
                while not self.has_ended():
                    self.flood()
            except KeyboardInterrupt:
                self.end_msg = "interrupted"
            except TimeoutException:
                self.end_msg = "timeout"
            except Exception as exc:  # pylint: disable=broad-except
                if self.quit:
                    self.end_msg = "quit received"
                elif self.read_error:
                    self.end_msg = "read error"
                else:
                    self.end_msg = "connection lost"
                self.end_exception = exc

    def end(self):
        """End client."""
        msg_exc = f" ({self.end_exception})" if self.end_exception else ""
        print(f"{self.end_msg}{msg_exc}")
        print(str(self.conn))
        if self.end_msg == "connection lost":
            print("Uh-oh! No quit received, client has crashed? Haha \\o/")
        self.conn.close()


def weercd_parser():
    """Return the parser for command line options."""
    epilog = """\
Note: the environment variable "WEERCD_OPTIONS" can be \
set with default options. Argument "@file.txt" can be used to read \
default options in a file."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        fromfile_prefix_chars="@",
        description="The WeeChat IRC testing server.",
        epilog=epilog,
    )
    parser.add_argument(
        "-c",
        "--maxchans",
        type=int,
        default=5,
        help="max number of channels to join",
    )
    parser.add_argument(
        "-C",
        "--maxclients",
        type=int,
        default=0,
        help="max number of clients (0 = unlimited)",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="debug output"
    )
    parser.add_argument(
        "-f",
        "--file",
        type=argparse.FileType("r"),
        help="send messages from file, instead of flooding "
        'the client (use "-" for stdin)',
    )
    parser.add_argument("-H", "--host", help="host for socket bind")
    parser.add_argument(
        "-n",
        "--maxnicks",
        type=int,
        default=100,
        help="max number of nicks per channel",
    )
    parser.add_argument(
        "-N",
        "--notice",
        metavar="NOTICE_TYPE",
        choices=["user", "channel"],
        default=["user", "channel"],
        nargs="*",
        help='notices to send: "user" (to user), "channel" (to channel)',
    )
    parser.add_argument(
        "-p", "--port", type=int, default=7777, help="port for socket bind"
    )
    parser.add_argument(
        "-s",
        "--sleep",
        type=float,
        default=0,
        help="sleep for select: delay between 2 messages sent "
        "to client (float, in seconds)",
    )
    parser.add_argument(
        "-t",
        "--time",
        type=int,
        default=0,
        help="stop flooding after this number of seconds (0 = unlimited)",
    )
    parser.add_argument(
        "-u",
        "--nickused",
        type=int,
        default=0,
        help="send 433 (nickname already in use) this number "
        "of times before accepting nick",
    )
    parser.add_argument("-v", "--version", action="version", version=VERSION)
    parser.add_argument(
        "-w",
        "--wait",
        type=float,
        default=0,
        help="time to wait before flooding client (float, in seconds)",
    )
    return parser


def main():
    """Main function."""
    # parse command line arguments
    parser = weercd_parser()
    args = parser.parse_args(
        shlex.split(os.getenv("WEERCD_OPTIONS") or "") + sys.argv[1:]
    )

    # welcome message, with options
    print(f"{NAME} {VERSION} - WeeChat IRC testing server")
    print(f"Options: {vars(args)}")

    # main loop
    count_clients = 0
    while args.maxclients == 0 or count_clients < args.maxclients:
        servsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            servsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servsock.bind((args.host or "", args.port))
            servsock.listen(1)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Socket error: {exc}")
            sys.exit(1)
        print(f"Listening on port {args.port} (ctrl-C to exit)")
        clientsock = None
        addr = None
        try:
            clientsock, addr = servsock.accept()
        except KeyboardInterrupt:
            servsock.close()
            sys.exit(0)
        print(f"Connection from {addr}")
        client = Client(clientsock, addr, args)
        client.run()
        client.end()
        del client
        count_clients += 1


if __name__ == "__main__":
    main()
