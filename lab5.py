"""
Networks and Network Security
Lab 5 - Distributed Sensor Network

NAME: Ezra Buenk
STUDENT ID: 15187814

DESCRIPTION:

"""
import sys
import struct
import socket
from random import randint, gauss
from gui import MainWindow
import sensor
from tkinter import TclError
import math


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


# Additional parameters to this function must always have a default value.
def main(mcast_addr, sensor_pos, sensor_strength, sensor_value,
         grid_size, ping_period):
    """
    mcast_addr: udp multicast (ip, port) tuple.
    sensor_pos: (x,y) sensor position tuple.
    sensor_strength: initial strength of the sensor ping (radius).
    sensor_value: initial temperature measurement of the sensor.
    grid_size: length of the grid (which is always square).
    ping_period: time in seconds between multicast pings.
    """

    # Create the multicast listener socket.
    mcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                          socket.IPPROTO_UDP)
    # Sets the socket address as reusable so you can run multiple instances
    # of the program on the same machine at the same time.
    mcast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Subscribe the socket to multicast messages from the given address.
    mreq = struct.pack('4sl', socket.inet_aton(mcast_addr[0]),
                       socket.INADDR_ANY)
    mcast.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    if sys.platform == 'win32':  # windows special case
        mcast.bind(('localhost', mcast_addr[1]))
    else:  # should work for everything else
        mcast.bind(mcast_addr)

    # Create the peer-to-peer socket.
    peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                         socket.IPPROTO_UDP)
    # Set the socket multicast TTL so it can send multicast messages.
    peer.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 5)
    # Bind the socket to a random port.
    if sys.platform == 'win32':  # windows special case
        peer.bind(('localhost', socket.INADDR_ANY))
    else:  # should work for everything else
        peer.bind(('', socket.INADDR_ANY))

    # make the gui.
    window = MainWindow()
    window.writeln('my address is %s:%s' % peer.getsockname())
    window.writeln('my position is (%s, %s)' % sensor_pos)

    # This is the event loop.
    try:
        while window.update():
            pass
    except TclError:
        pass


# Program entry point.
# You may add additional commandline arguments, but your program
# should be able to run without specifying them
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--group', help='multicast group', default='224.1.1.1',
                   type=str)
    p.add_argument('--port', help='multicast port', default=50000, type=int)
    p.add_argument('--pos', help='x,y sensor position', type=str)
    p.add_argument('--strength', help='sensor strength', default=64,
                   type=int)
    p.add_argument('--value', help='sensor measurement value', type=float)
    p.add_argument('--grid', help='size of grid', default=128, type=int)
    p.add_argument('--period', help='period between autopings (0=off)',
                   default=10, type=int)
    args = p.parse_args(sys.argv[1:])
    if args.pos:
        pos = tuple(int(n) for n in args.pos.split(',')[:2])
    else:
        pos = random_position(args.grid)
    value = args.value if args.value is not None else gauss(20, 2)
    mcast_addr = (args.group, args.port)
    main(mcast_addr, pos, args.strength, value, args.grid, args.period)
