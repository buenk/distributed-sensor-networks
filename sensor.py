"""
Networks and Network Security
Lab 5 - Distributed Sensor Network

NAME: Ezra Buenk
STUDENT ID: 15817814

DESCRIPTION: Definitions and message format
"""

import struct

# These are the message types.
MSG_PING = 0  # Multicast ping.
MSG_PONG = 1  # Unicast pong.
MSG_ECHO = 2  # Unicast echo.
MSG_ECHO_REPLY = 3  # Unicast echo reply.
# TODO: You may define your own message types if needed.

# These are the echo operations.
OP_NOOP = 0  # Do nothing.
OP_SIZE = 1  # Compute the size of network.
OP_UPDATE = 2  # Force update the network.
OP_ROUTE_HOPS = 3
OP_ROUTE_STRENGTH = 4
OP_ROUTE_FETCH = 5

# This is used to pack message fields into a binary format.
message_format = struct.Struct("!iiiiiiiiiif")

# Length of a message in bytes.
message_length = message_format.size


def message_encode(
    type,
    sequence,
    initiator,
    neighbor,
    target=(0, 0),
    operation=0,
    strength=0,
    payload=0,
):
    """
    Encodes message fields into a binary format.
    type: The message type.
    sequence: The wave sequence number.
    initiator: An (x, y) tuple that contains the initiator's position.
    neighbor: An (x, y) tuple that contains the neighbor's position.
    operation: The echo operation.
    strength: The strength of initiator
    payload: Echo operation data (a number and a decaying rate).
    Returns: A binary string in which all parameters are packed.
    """
    ix, iy = initiator
    nx, ny = neighbor
    tx, ty = target
    return message_format.pack(
        type, sequence, ix, iy, nx, ny, tx, ty, operation, strength, payload
    )


def message_decode(buffer):
    """
    Decodes a binary message string to Python objects.
    buffer: The binary string to decode.
    Returns: A tuple containing all the unpacked message fields.
    """
    type, sequence, ix, iy, nx, ny, tx, ty, operation, strength, payload = (
        message_format.unpack(buffer)
    )
    return (
        type,
        sequence,
        (ix, iy),
        (nx, ny),
        (tx, ty),
        operation,
        strength,
        payload,
    )
