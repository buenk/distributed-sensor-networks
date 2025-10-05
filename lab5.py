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


@dataclass
class Wave:
    children_waiting: set[tuple[int, int]]
    operation: int = sensor.OP_NOOP
    parent: tuple[int, int] | None = None
    payload_sum: int = 0
    target: tuple[int, int] | None = None


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
    def __init__(
        self, mcast_addr, position, strength, value, ping_period, grid_size
    ):
        self.listener = MulticastListener(mcast_addr)
        self.peer_messenger = PeerMessenger()

        self.mcast_addr = mcast_addr
        self.position = position
        self.strength = strength
        self.value = value
        self.ping_period = ping_period
        self.grid_size = grid_size

        self.neighbours: dict[tuple[int, int], Neighbour] = {}
        self.next_ping_at = time.time()
        self.window = None

    def start(self):
        self.peer_messenger.start()
        self.listener.start()

        ip, port = self.peer_messenger.get_address()
        self.ip = ip
        self.port = port

        # make the gui.
        self.window = MainWindow()
        self.window.writeln(
            "my address is %s:%s" % self.peer_messenger.get_address()
        )
        self.window.writeln("my position is (%s, %s)" % self.position)

        self.wave_controller = EchoWaveController(
            self, self.peer_messenger, self.window.writeln
        )

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
        sockets = [self.listener.socket, self.peer_messenger.socket]

        # Read any incoming messages
        rlist, _, _ = select.select(sockets, [], [], 0.05)

        if self.listener.socket in rlist:
            message, address = self.listener.poll()
            message_type = message[0]

            if message_type == sensor.MSG_PING:
                self._handle_ping(message, address)

        if self.peer_messenger.socket in rlist:
            message, address = self.peer_messenger.poll()
            message_type = message[0]

            if message_type == sensor.MSG_PONG:
                self._handle_pong(message, address)
            elif message_type == sensor.MSG_ECHO:
                self.wave_controller.handle_echo(message, address)
            elif message_type == sensor.MSG_ECHO_REPLY:
                self.wave_controller.handle_echo_reply(message, address)

    def _periodic_ping(self):
        now = time.time()
        if self.ping_period > 0 and now >= self.next_ping_at:
            self.peer_messenger.send_ping(
                self.mcast_addr, self.position, self.position, self.strength
            )
            self.next_ping_at = now + self.ping_period

        # remove old/stale neighbours
        ttl = 3 * self.ping_period
        for pos in list(self.neighbours.keys()):
            if now - self.neighbours[pos].last_seen > ttl:
                del self.neighbours[pos]

    def _handle_pong(self, decoded_message, address):
        neighbour_position = decoded_message[3]
        if neighbour_position == self.position:
            return

        neighbour_strength = decoded_message[6]

        distance = calculate_distance(self.position, neighbour_position)
        if distance <= neighbour_strength:
            self.neighbours[neighbour_position] = Neighbour(
                ip=address[0],
                port=address[1],
                strength=neighbour_strength,
                distance=distance,
                last_seen=time.time(),
            )

    def _handle_ping(self, decoded_message, address):
        initiator_position = decoded_message[2]
        if initiator_position == self.position:
            return

        initiator_strength = decoded_message[6]

        distance = calculate_distance(self.position, initiator_position)
        if distance <= initiator_strength:
            self.peer_messenger.send_pong(
                address, initiator_position, self.position, self.strength
            )

    def _handle_gui_commands(self):
        line = self.window.getline()
        if not line:
            return
        parts = line.strip().split(" ")
        cmd = parts[0].lower()

        if cmd == "properties":
            self.window.writeln(
                f"{self.position};{self.value};{self.strength};{self.ip}:{self.port}"
            )
        elif cmd == "ping":
            self.peer_messenger.send_ping(
                self.mcast_addr, self.position, self.position, self.strength
            )
        elif cmd == "list":
            for location, neighbour in self.neighbours.items():
                self.window.writeln(f"{location};{neighbour.distance}")
                # TODO: Order this by nearest
        elif cmd == "move":
            x = int(parts[1])
            y = int(parts[2])
            if len(parts) != 3:
                self.window.writeln("usage: move <x> <y>")
            elif x > self.grid_size or y > self.grid_size:
                self.window.writeln("x and y must be within grid")
            else:
                self.position = (x, y)
                self._periodic_ping()  # Re-ping to adjust neighbours
        elif cmd == "strength":
            if len(parts) != 2:
                self.window.writeln("usage: strength <new_value>")
            elif int(parts[1]) < 0:
                self.window.writeln("strength must be greater than 0")
            else:
                self.strength = int(parts[1])
        elif cmd == "echo":
            self.wave_controller.start_echo_wave()
        elif cmd == "size":
            self.wave_controller.start_echo_wave(sensor.OP_SIZE)


class MulticastListener:
    def __init__(self, mcast_addr):
        self.mcast_addr = mcast_addr
        self._sock = None

    def start(self):
        # Create the multicast listener socket.
        self._sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # Sets the socket address as reusable so you can run multiple instances
        # of the program on the same machine at the same time.
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Subscribe the socket to multicast messages from the given address.
        mreq = struct.pack(
            "4sl", socket.inet_aton(self.mcast_addr[0]), socket.INADDR_ANY
        )
        self._sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
        )
        if sys.platform == "win32":  # windows special case
            self._sock.bind(("localhost", self.mcast_addr[1]))
        else:  # should work for everything else
            self._sock.bind(self.mcast_addr)

    def poll(self):
        data, address = self._sock.recvfrom(4096)

        try:
            decoded_message = sensor.message_decode(data)
        except Exception:
            self.window.writeln(
                "Error: Received message was not in the proper format."
            )
            return

        return decoded_message, address

    @property
    def socket(self):
        return self._sock


class PeerMessenger:
    def __init__(self):
        self._sock = None

    def start(self):
        # Create the peer-to-peer socket.
        self._sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # Set the socket multicast TTL so it can send multicast messages.
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 5)

        # Bind the socket to a random port.
        if sys.platform == "win32":  # windows special case
            self._sock.bind(("localhost", socket.INADDR_ANY))
        else:  # should work for everything else
            self._sock.bind(("", socket.INADDR_ANY))

    def poll(self):
        data, address = self._sock.recvfrom(4096)

        try:
            decoded_message = sensor.message_decode(data)
        except Exception:
            self.window.writeln(
                "Error: Received message was not in the proper format."
            )
            return

        return decoded_message, address

    def get_address(self):
        ip, port = self._sock.getsockname()
        return ip, port

    def send_pong(
        self, address, initiator_position, sender_position, strength
    ):
        msg = sensor.message_encode(
            sensor.MSG_PONG,
            0,
            initiator_position,
            sender_position,
            (0, 0),
            0,
            strength,
            0,
        )

        self._sock.sendto(msg, address)

    def send_ping(
        self, address, initiator_position, sender_position, strength
    ):
        msg = sensor.message_encode(
            sensor.MSG_PING,
            0,
            initiator_position,
            sender_position,
            (0, 0),
            0,
            strength,
            0,
        )

        self._sock.sendto(msg, address)

    def send_echo(
        self,
        address,
        initiator_position,
        sequence_number,
        sender_position,
        strength,
        operation=sensor.OP_NOOP,
        payload=0,
    ):
        msg = sensor.message_encode(
            sensor.MSG_ECHO,
            sequence_number,
            initiator_position,
            sender_position,
            (0, 0),
            operation,
            strength,
            payload,
        )

        self._sock.sendto(msg, address)

    def send_echo_reply(
        self,
        address,
        initiator_position,
        sequence_number,
        sender_position,
        strength,
        operation=sensor.OP_NOOP,
        payload=0,
    ):
        msg = sensor.message_encode(
            sensor.MSG_ECHO_REPLY,
            sequence_number,
            initiator_position,
            sender_position,
            (0, 0),
            operation,
            strength,
            payload,
        )

        self._sock.sendto(msg, address)

    @property
    def socket(self):
        return self._sock


class EchoWaveController:
    def __init__(self, node: SensorNode, messenger: PeerMessenger, log):
        self.node = node
        self.msg = messenger
        self.log = log
        self.waves_sent = 0
        self.ongoing_waves: dict[tuple[tuple[int, int], int], Wave] = {}

    def start_echo_wave(self, operation=sensor.OP_NOOP):
        children = set(self.node.neighbours.keys())
        origin = self.node.position
        print(f"{origin} - Initiating echo wave.")

        self.ongoing_waves[(origin, self.waves_sent)] = Wave(
            parent=None, children_waiting=children, operation=operation
        )

        if not children:
            if operation == sensor.OP_SIZE:
                self.log("size=1")
            else:
                self.log(f"The wave {self.waves_sent} has decided.")

            del self.ongoing_waves[(origin, self.waves_sent)]

        for neighbour in self.node.neighbours.values():
            self.msg.send_echo(
                (neighbour.ip, neighbour.port),
                origin,
                self.waves_sent,
                origin,
                self.node.strength,
                operation,
            )

        self.waves_sent += 1

    def handle_echo(self, decoded_message, address):
        initiator_position = decoded_message[2]
        sequence_number = decoded_message[1]
        sender_position = decoded_message[3]
        operation = decoded_message[5]

        origin = self.node.position

        # Check if we've already seen this wave.
        if (initiator_position, sequence_number) not in self.ongoing_waves:
            print(f"{origin} - Not seen this wave.")
            children = set(self.node.neighbours.keys()) - {sender_position}

            # Add wave to state.
            self.ongoing_waves[(initiator_position, sequence_number)] = Wave(
                parent=sender_position,
                children_waiting=children,
                operation=operation,
            )
            print(f"{origin} - Added wave to state.")

            # No children (leaf node), ECHO_REPLY immediately.
            if not children:
                print(f"{origin} - No children.")
                parent_address = (
                    self.node.neighbours[sender_position].ip,
                    self.node.neighbours[sender_position].port,
                )

                self.msg.send_echo_reply(
                    parent_address,
                    initiator_position,
                    sequence_number,
                    origin,
                    self.node.strength,
                    operation,
                    1 if operation == sensor.OP_SIZE else 0,
                )

                return

            # Forward ECHO message to children only.
            for child_position in children:
                print(f"{origin} - Sent echo messages to children.")
                child = self.node.neighbours[child_position]
                self.msg.send_echo(
                    (child.ip, child.port),
                    initiator_position,
                    sequence_number,
                    origin,
                    self.node.strength,
                    operation,
                )

            return

        # Already participating in wave, send ECHO_REPLY.
        self.msg.send_echo_reply(
            address,
            initiator_position,
            sequence_number,
            origin,
            self.node.strength,
            operation,
        )
        print(f"{origin} - Already participating in wave, sent echo reply.")

    def handle_echo_reply(self, decoded_message, address):
        initiator_position = decoded_message[2]
        sequence_number = decoded_message[1]
        sender_position = decoded_message[3]
        operation = decoded_message[5]
        payload = decoded_message[7]

        wave = self.ongoing_waves[(initiator_position, sequence_number)]
        wave.children_waiting.discard(sender_position)

        wave.payload_sum += payload if operation == sensor.OP_SIZE else 0
        upstream_payload = wave.payload_sum + 1

        # Check if children waiting set is empty
        if not wave.children_waiting:
            if wave.parent is None:
                if operation == sensor.OP_SIZE:
                    self.log(f"size={upstream_payload}")
                else:
                    self.log(f"The wave {sequence_number} has decided.")
            else:
                self.log(
                    f"{(sequence_number, initiator_position)}: Received from all neighbours."
                )

                parent_position = wave.parent
                parent_address = (
                    self.node.neighbours[parent_position].ip,
                    self.node.neighbours[parent_position].port,
                )

                self.msg.send_echo_reply(
                    parent_address,
                    initiator_position,
                    sequence_number,
                    self.node.position,
                    self.node.strength,
                    operation,
                    upstream_payload if operation == sensor.OP_SIZE else 0,
                )

            del self.ongoing_waves[(initiator_position, sequence_number)]


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
        mcast_addr,
        sensor_pos,
        sensor_strength,
        sensor_value,
        ping_period,
        grid_size,
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
