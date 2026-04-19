# Distributed Sensor Network

UvA project implementing a distributed sensor network with peer discovery and distributed computation via the echo wave algorithm.

Each node is a simulated sensor on a 2D grid. Nodes discover each other using UDP multicast pings, maintain a neighbour list based on signal strength and distance, and can run distributed algorithms across the live network topology.

## Concepts Learned

- **UDP multicast** for decentralised peer discovery (ping/pong)
- **Echo wave algorithm** — a classic distributed algorithm where a wave propagates through the spanning tree of a network, collects data at leaf nodes, and rolls back up to the initiator (used here to count live nodes)
- **Non-blocking I/O** with `select()` to multiplex socket reads and a Tkinter GUI in a single event loop
- How network topology emerges dynamically from signal strength and Euclidean distance, with stale neighbours timing out automatically

## Running

**Single node** (random position, default settings):
```sh
python3 lab5.py
```

**Single node** (manual config):
```sh
python3 lab5.py --pos 10,20 --strength 64 --period 5
```

**Five nodes at once** (each gets its own GUI window):
```sh
bash start_network.sh
```

All nodes on the same machine automatically join the multicast group `224.1.1.1:50000`.

### CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--group` | `224.1.1.1` | Multicast group IP |
| `--port` | `50000` | Multicast port |
| `--pos` | random | `x,y` position on the grid |
| `--strength` | `64` | Signal radius (neighbours within this distance are visible) |
| `--value` | random ~20°C | Sensor measurement value |
| `--grid` | `128` | Grid size (NxN) |
| `--period` | `10` | Seconds between auto-pings (`0` to disable) |

## GUI Commands

Once a node window is open, type commands into the text field and press **OK** (or Enter):

| Command | Description |
|---|---|
| `properties` | Print this node's position, value, strength, and address |
| `ping` | Manually broadcast a ping to discover neighbours |
| `list` | List current neighbours sorted by distance |
| `move <x> <y>` | Move this node to a new position and re-ping |
| `strength <n>` | Update signal strength (affects neighbour visibility) |
| `echo` | Run an echo wave across the network (NOOP) |
| `size` | Run an echo wave and report the number of reachable nodes |
