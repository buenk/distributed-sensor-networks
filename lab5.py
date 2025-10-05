"""
Networks and Network Security
Lab 5 - Distributed Sensor Network

NAME: Ezra Buenk
STUDENT ID: 15187814

DESCRIPTION:

"""

from random import randint, gauss
from gui import MainWindow
from tkinter import TclError
from dataclasses import dataclass

import sys
import struct
import socket
import sensor
import math
import select
import time


@dataclass
class Neighbour:
    ip: str
    port: int
    strength: int
    distance: float
    last_seen: float


# Get random position in NxN grid.
def random_position(n):
    x = randint(0, n)
    y = randint(0, n)
    return (x, y)


def calculate_distance(point_a, point_b):
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]

    distance = math.hypot(dx, dy)
    return distance


class SensorNode:
    def __init__(self, mcast_addr, position, strength, value, ping_period):
        self.mcast_addr = mcast_addr
        self.position = position
        self.strength = strength
        self.value = value
        self.ping_period = ping_period

        self.neighbours: dict[tuple[int, int], Neighbour] = {}
        self.next_ping_at = (
            time.time() + ping_period if ping_period > 0 else None
        )

        # Will be defined in start
        self.mcast = None
        self.peer = None
        self.window = None

    def start(self):
        # Create the multicast listener socket.
        self.mcast = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # Sets the socket address as reusable so you can run multiple instances
        # of the program on the same machine at the same time.
        self.mcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Subscribe the socket to multicast messages from the given address.
        mreq = struct.pack(
            "4sl", socket.inet_aton(self.mcast_addr[0]), socket.INADDR_ANY
        )
        self.mcast.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
        )
        if sys.platform == "win32":  # windows special case
            self.mcast.bind(("localhost", self.mcast_addr[1]))
        else:  # should work for everything else
            self.mcast.bind(self.mcast_addr)

        # Create the peer-to-peer socket.
        self.peer = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # Set the socket multicast TTL so it can send multicast messages.
        self.peer.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 5)

        # Bind the socket to a random port.
        if sys.platform == "win32":  # windows special case
            self.peer.bind(("localhost", socket.INADDR_ANY))
        else:  # should work for everything else
            self.peer.bind(("", socket.INADDR_ANY))

        # Get the IP and port of the socket.
        ip, port = self.peer.getsockname()
        self.ip = ip
        self.port = port

        # make the gui.
        self.window = MainWindow()
        self.window.writeln("my address is %s:%s" % self.peer.getsockname())
        self.window.writeln("my position is (%s, %s)" % self.position)

        # This is the event loop.
        try:
            while self.window.update():
                self._handle_incoming_messages()
                self._periodic_ping()
                self._handle_gui_commands()

            # TODO: the periodic ping

        except TclError:
            pass

    def _handle_incoming_messages(self):
        # Read any incoming messages
        rlist, _, _ = select.select([self.mcast, self.peer], [], [], 0.05)
        for sock in rlist:
            data, address = sock.recvfrom(4096)

            try:
                decoded_message = sensor.message_decode(data)
            except Exception:
                print("Error: Received was not in the proper format.")
                continue

            message_type = decoded_message[0]

            if message_type == sensor.MSG_PING and sock is self.mcast:
                self._handle_ping(decoded_message, address)
            elif message_type == sensor.MSG_PONG and sock is self.peer:
                self._handle_pong(decoded_message, address)
            else:
                pass

    def _periodic_ping(self):
        now = time.time()
        if self.ping_period > 0 and now >= self.next_ping_at:
            self.send_ping(self.mcast_addr)
            self.next_ping_at = now + self.ping_period

    def send_pong(self, address, initiator_position):
        msg = sensor.message_encode(
            sensor.MSG_PONG,
            0,
            initiator_position,
            self.position,
            (0, 0),
            0,
            self.strength,
            0,
        )

        self.peer.sendto(msg, address)

    def send_ping(self, address):
        msg = sensor.message_encode(
            sensor.MSG_PING,
            0,
            self.position,
            self.position,
            (0, 0),
            0,
            self.strength,
            0,
        )

        self.peer.sendto(msg, address)

    def _handle_pong(self, decoded_message, address):
        neighbour_position = decoded_message[3]
        distance = calculate_distance(self.position, neighbour_position)
        if distance <= self.strength:
            self.neighbours[neighbour_position] = Neighbour(
                ip=address[0],
                port=address[1],
                strength=self.strength,
                distance=distance,
                last_seen=time.time(),
            )

    def _handle_ping(self, decoded_message, address):
        initiator_position = decoded_message[2]
        initiator_strength = decoded_message[6]
        distance = calculate_distance(self.position, initiator_position)
        if distance <= initiator_strength:
            self.send_pong(address, initiator_position)

    def _handle_gui_commands(self):
        line = self.window.getline()
        if not line:
            return
        parts = line.strip().split(" ")
        cmd = parts[0].lower()

        if cmd == "properties":
            self.window.writeln(
                f"{self.position};{self.value};{self.strength};{self.ip};{self.port}"
            )


# Additional parameters to this function must always have a default value.
def main(
    mcast_addr,
    sensor_pos,
    sensor_strength,
    sensor_value,
    grid_size,
    ping_period,
):
    """
    mcast_addr: udp multicast (ip, port) tuple.
    sensor_pos: (x,y) sensor position tuple.
    sensor_strength: initial strength of the sensor ping (radius).
    sensor_value: initial temperature measurement of the sensor.
    grid_size: length of the grid (which is always square).
    ping_period: time in seconds between multicast pings.
    """

    new_sensor = SensorNode(
        mcast_addr, sensor_pos, sensor_strength, sensor_value, ping_period
    )

    new_sensor.start()


# Program entry point.
# You may add additional commandline arguments, but your program
# should be able to run without specifying them
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "--group", help="multicast group", default="224.1.1.1", type=str
    )
    p.add_argument("--port", help="multicast port", default=50000, type=int)
    p.add_argument("--pos", help="x,y sensor position", type=str)
    p.add_argument("--strength", help="sensor strength", default=64, type=int)
    p.add_argument("--value", help="sensor measurement value", type=float)
    p.add_argument("--grid", help="size of grid", default=128, type=int)
    p.add_argument(
        "--period",
        help="period between autopings (0=off)",
        default=10,
        type=int,
    )
    args = p.parse_args(sys.argv[1:])
    if args.pos:
        pos = tuple(int(n) for n in args.pos.split(",")[:2])
    else:
        pos = random_position(args.grid)
    value = args.value if args.value is not None else gauss(20, 2)
    mcast_addr = (args.group, args.port)
    main(mcast_addr, pos, args.strength, value, args.grid, args.period)
