#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2019 Sébastien Helleu <flashcode@flashtux.org>
#
# This file is part of weercd, the WeeChat IRC testing server.
#
# weercd is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# weercd is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with weercd.  If not, see <https://www.gnu.org/licenses/>.
#

"""WeeChat IRC testing server."""

import argparse
import os
import random
import re
import select
import shlex
import socket
import string
import sys
import time
import traceback

NAME = 'weercd'
VERSION = '1.0-dev'


def random_string(max_length, spaces=False):
    """Return a random string (random length and content)."""
    length = random.randint(1, max_length)
    chars = (string.ascii_uppercase
             + string.ascii_lowercase
             + string.digits
             + (' ' if spaces else ''))
    return ''.join(random.choice(chars) for x in range(length))


def random_host():
    """Return a random host name."""
    return f'{random_string(10)}@{random_string(10)}'


def random_channel():
    """Return a random channel name."""
    return f'#{random_string(25)}'


class Client:  # pylint: disable=too-many-instance-attributes
    """A client of weercd server."""

    def __init__(self, sock, addr, args):
        self.sock = sock
        self.addr = addr
        self.args = args
        self.name = NAME
        self.version = VERSION
        self.nick = ''
        self.nicknumber = 0
        self.channels = {}
        self.lastbuf = ''
        self.incount = 0
        self.outcount = 0
        self.inbytes = 0
        self.outbytes = 0
        self.quit = False
        self.endmsg = ''
        self.endexcept = None
        self.starttime = time.time()
        self.connect()

    def run(self):
        """Execute the action asked for the client."""
        if self.quit:
            return

        # send commands from file (which can be stdin)
        if self.args.file:
            self.send_file()
            return

        # flood the client
        if self.args.wait > 0:
            print(f'Waiting {self.args.wait} seconds')
            time.sleep(self.args.wait)
        sys.stdout.write('Flooding client..')
        sys.stdout.flush()
        try:
            while not self.quit:
                self.flood()
        except Exception as exc:  # pylint: disable=broad-except
            if self.quit:
                self.endmsg = 'quit received'
            else:
                self.endmsg = 'connection lost'
            self.endexcept = exc
        except KeyboardInterrupt:
            self.endmsg = 'interrupted'
        else:
            self.endmsg = 'quit received'

    def random_nick(self, with_number=False):
        """Return a random nick name."""
        if with_number:
            self.nicknumber += 1
            return f'{random_string(5)}{self.nicknumber}'
        return random_string(10)

    def send(self, data):
        """Send one message to client."""
        if self.args.debug:
            print(f'<-- {data}')
        msg = data + '\r\n'
        self.outbytes += len(msg)
        self.sock.send(msg.encode('UTF-8'))
        self.outcount += 1

    # pylint: disable=too-many-arguments
    def send_command(self, command, data, nick=None, host='', target=None):
        """Send an IRC command to the client."""
        if nick is None:
            nick = self.name
        if target is None:
            target = self.nick
        sender = f':{nick}{"!" if host else ""}{host}'
        target = f'{" " if target else ""}{target}'
        data = f'{" :" if data else ""}{data}'
        self.send(f'{sender} {command}{target}{data}')

    def recv(self, data):
        """Read one IRC message from client."""
        if self.args.debug:
            print(f'--> {data}')
        if data.startswith('PING '):
            args = data[5:]
            if args[0] == ':':
                args = args[1:]
            self.send(f'PONG :{args}')
        elif data.startswith('NICK '):
            self.nick = data[5:]
        elif data.startswith('PART '):
            match = re.search('^PART :?(#[^ ]+)', data)
            if match:
                channel = match.group(1)
                if channel in self.channels:
                    del self.channels[channel]
        elif data.startswith('QUIT '):
            self.quit = True
        self.incount += 1

    def read(self, timeout):
        """Read raw data received from client."""
        inr = select.select([self.sock], [], [], timeout)[0]
        if inr:
            data = self.sock.recv(4096)
            if data:
                data = data.decode('UTF-8')
                self.inbytes += len(data)
                data = self.lastbuf + data
                while True:
                    pos = data.find('\r\n')
                    if pos < 0:
                        break
                    self.recv(data[0:pos])
                    data = data[pos + 2:]
                self.lastbuf = data

    def connect(self):
        """Inform the client that the connection is OK."""
        try:
            count = self.args.nickused
            while self.nick == '':
                self.read(0.1)
                if self.nick and count > 0:
                    self.send_command('433', 'Nickname is already in use.',
                                      target=f'* {self.nick}')
                    self.nick = ''
                    count -= 1
            self.send_command('001', 'Welcome to the WeeChat IRC server')
            self.send_command('002',
                              f'Your host is {self.name}, '
                              f'running version {self.version}')
            self.send_command('003', 'Are you solid like a rock?')
            self.send_command('004', 'Let\'s see!')
        except KeyboardInterrupt:
            self.quit = True
            self.endmsg = 'interrupted'
            return

    def channel_random_nick(self, channel):
        """Return a random nick of a channel."""
        if len(self.channels[channel]) < 2:
            return None
        rnick = self.nick
        while rnick == self.nick:
            rnick = self.channels[channel][
                random.randint(0, len(self.channels[channel]) - 1)]
        return rnick

    def flood_self_join(self):
        """Self join on a new channel."""
        channel = random_channel()
        if channel in self.channels:
            return
        self.send_command('JOIN', channel,
                          nick=self.nick, host=self.addr[0], target='')
        self.send_command('353', f'@{self.nick}',
                          target=f'{self.nick} = {channel}')
        self.send_command('366', 'End of /NAMES list.',
                          target=f'{self.nick} {channel}')
        self.channels[channel] = [self.nick]

    def flood_user_notice(self):
        """Notice for the user."""
        self.send_command('NOTICE', random_string(400, spaces=True),
                          nick=self.random_nick(), host=random_host())

    def flood_channel_join(self, channel):
        """Join of a user in a channel."""
        if len(self.channels[channel]) >= self.args.maxnicks:
            return
        newnick = self.random_nick(with_number=True)
        self.send_command('JOIN', channel,
                          nick=newnick, host=random_host(), target='')
        self.channels[channel].append(newnick)

    def flood_channel_part(self, channel):
        """Part or quit of a user in a channel."""
        if not self.channels[channel]:
            return
        rnick = self.channel_random_nick(channel)
        if not rnick:
            return
        if random.randint(1, 2) == 1:
            self.send_command('PART', channel,
                              nick=rnick, host=random_host(), target='')
        else:
            self.send_command('QUIT', random_string(30),
                              nick=rnick, host=random_host(), target='')
        self.channels[channel].remove(rnick)

    def flood_channel_kick(self, channel):
        """Kick of a user in a channel."""
        if not self.channels[channel]:
            return
        rnick1 = self.channel_random_nick(channel)
        rnick2 = self.channel_random_nick(channel)
        if rnick1 and rnick2 and rnick1 != rnick2:
            self.send_command('KICK', random_string(50),
                              nick=rnick1, host=random_host(),
                              target=f'{channel} {rnick2}')
            self.channels[channel].remove(rnick2)

    def flood_channel_message(self, channel):
        """Message from a user in a channel."""
        if not self.channels[channel]:
            return
        rnick = self.channel_random_nick(channel)
        if not rnick:
            return
        msg = random_string(400, spaces=True)
        if 'channel' in self.args.notice and random.randint(1, 100) == 100:
            # notice for channel
            self.send_command('NOTICE', msg,
                              nick=rnick, host=random_host(), target=channel)
        else:
            # add random highlight
            if random.randint(1, 100) == 100:
                msg = f'{self.nick}: {msg}'
            action2 = random.randint(1, 50)
            if action2 == 1:
                # CTCP action (/me)
                msg = f'\x01ACTION {msg}\x01'
            elif action2 == 2:
                # CTCP version
                msg = '\x01VERSION\x01'
            self.send_command('PRIVMSG', msg,
                              nick=rnick, host=random_host(), target=channel)

    def flood(self):
        """Yeah, funny stuff here! Flood the client!"""
        self.read(self.args.sleep)
        # global actions
        action = random.randint(1, 2)
        if action == 1 and len(self.channels) < self.args.maxchans:
            self.flood_self_join()
        elif action == 2 and 'user' in self.args.notice:
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
        if self.outcount % 1000 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()

    def send_file(self):  # pylint: disable=too-many-branches
        """Send messages from a file to client."""
        stdin = self.args.file == sys.stdin
        count = 0
        self.read(0.2)
        try:  # pylint: disable=too-many-nested-blocks
            while True:
                # display the prompt if we are reading in stdin
                if stdin:
                    sys.stdout.write('Message to send to client '
                                     '(/help for help): ')
                    sys.stdout.flush()
                message = self.args.file.readline()
                if not message:
                    break
                if sys.version_info < (3,):
                    message = message.decode('UTF-8')
                message = message.rstrip('\n')
                if message:
                    if message.startswith('/') and message[1:2] != '/':
                        command = message[1:]
                        if command == 'help':
                            pass
                    elif not message.startswith('//'):
                        self.send(message.format(self=self))
                        count += 1
                self.read(0.1 if stdin else self.args.sleep)
        except IOError as exc:
            self.endmsg = f'unable to read file {self.args.file}'
            self.endexcept = exc
            return
        except KeyboardInterrupt:
            self.endmsg = 'interrupted'
            return
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc()
            self.endmsg = 'connection lost'
            return
        finally:
            sys.stdout.write('\n')
            sys.stdout.write(f'{count} messages sent '
                             f'from {"stdin" if stdin else "file"}, '
                             f'press Enter to exit')
            sys.stdout.flush()
            try:
                sys.stdin.readline()
            except Exception:  # pylint: disable=broad-except
                pass

    def stats(self):
        """Display some statistics about data exchanged with the client."""
        msgexcept = ''
        if self.endexcept:
            msgexcept = f'({self.endexcept})'
        print(f'{self.endmsg} {msgexcept}')
        elapsed = time.time() - self.starttime
        countrate = self.outcount / elapsed
        bytesrate = self.outbytes / elapsed
        print(f'Elapsed: {elapsed:.1f}s - '
              f'packets: in:{self.incount}, out:{self.outcount} '
              f'({countrate:.0f}/s) - '
              f'bytes: in:{self.inbytes}, out: {self.outbytes} '
              f'({bytesrate:.0f}/s)')
        if self.endmsg == 'connection lost':
            print('Uh-oh! No quit received, client has crashed? Haha \\o/')

    def __del__(self):
        self.stats()
        print(f'Closing connection with {self.addr}')
        self.sock.close()


def weercd_parser():
    """Return the parser for command line options."""
    epilog = """\
Note: the environment variable "WEERCD_OPTIONS" can be \
set with default options. Argument "@file.txt" can be used to read \
default options in a file."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        fromfile_prefix_chars='@',
        description='The WeeChat IRC testing server.',
        epilog=epilog,
    )
    parser.add_argument('-H', '--host', help='host for socket bind')
    parser.add_argument('-p', '--port', type=int, default=7777,
                        help='port for socket bind')
    parser.add_argument('-f', '--file', type=argparse.FileType('r'),
                        help='send messages from file, instead of flooding '
                        'the client (use "-" for stdin)')
    parser.add_argument('-c', '--maxchans', type=int, default=5,
                        help='max number of channels to join')
    parser.add_argument('-n', '--maxnicks', type=int, default=100,
                        help='max number of nicks per channel')
    parser.add_argument('-u', '--nickused', type=int, default=0,
                        help='send 433 (nickname already in use) this number '
                        'of times before accepting nick')
    parser.add_argument('-N', '--notice', metavar='NOTICE_TYPE',
                        choices=['user', 'channel'],
                        default=['user', 'channel'], nargs='*',
                        help='notices to send: "user" (to user), "channel" '
                        '(to channel)')
    parser.add_argument('-s', '--sleep', type=float, default=0,
                        help='sleep for select: delay between 2 messages sent '
                        'to client (float, in seconds)')
    parser.add_argument('-w', '--wait', type=float, default=0,
                        help='time to wait before flooding client (float, '
                        'in seconds)')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='debug output')
    parser.add_argument('-v', '--version', action='version', version=VERSION)
    return parser


def main():
    """Main function."""
    # parse command line arguments
    parser = weercd_parser()
    args = parser.parse_args(shlex.split(os.getenv('WEERCD_OPTIONS') or '')
                             + sys.argv[1:])

    # welcome message, with options
    print(f'{NAME} {VERSION} - WeeChat IRC testing server')
    print(f'Options: {vars(args)}')

    # main loop
    while True:
        servsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            servsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servsock.bind((args.host or '', args.port))
            servsock.listen(1)
        except Exception as exc:  # pylint: disable=broad-except
            print(f'Socket error: {exc}')
            sys.exit(1)
        print(f'Listening on port {args.port} (ctrl-C to exit)')
        clientsock = None
        addr = None
        try:
            clientsock, addr = servsock.accept()
        except KeyboardInterrupt:
            servsock.close()
            sys.exit(0)
        print(f'Connection from {addr}')
        client = Client(clientsock, addr, args)
        client.run()
        del client
        # no loop if message were sent from a file
        if args.file:
            break


if __name__ == "__main__":
    main()
