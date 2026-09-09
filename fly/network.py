"""Data model for the Fly-in drone routing network.

Defines the zone types, individual zones, connections between them,
and the network that aggregates everything into a queryable graph.
"""

from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    """Movement type of a zone, which drives its traversal cost."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def move_cost(self) -> int:
        """Return the number of turns required to enter this zone."""
        return 2 if self is ZoneType.RESTRICTED else 1

    @property
    def is_passable(self) -> bool:
        """Return ``True`` if a drone may enter this zone."""
        return self is not ZoneType.BLOCKED


@dataclass
class Zone:
    """A single zone (node) of the network."""

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1

    @property
    def move_cost(self) -> int:
        """Return the turn cost to enter this zone."""
        return self.zone_type.move_cost


@dataclass
class Connection:
    """A bidirectional link (edge) between two zones."""

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> frozenset[str]:
        """Return an order-independent identity for this connection."""
        return frozenset((self.zone_a, self.zone_b))


class Network:
    """The whole map: drones, zones, connections and adjacency."""

    def __init__(self) -> None:
        """Initialise an empty network."""
        self.nb_drones: int = 0
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.adjacency: dict[str, list[str]] = {}
        self.start: str | None = None
        self.end: str | None = None
        self._conn_keys: set[frozenset[str]] = set()

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone and create its (empty) adjacency entry."""
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

    def add_connection(self, conn: Connection) -> None:
        """Register a connection and update both adjacency lists."""
        self.connections.append(conn)
        self._conn_keys.add(conn.key)
        self.adjacency[conn.zone_a].append(conn.zone_b)
        self.adjacency[conn.zone_b].append(conn.zone_a)

    def has_connection(self, zone_a: str, zone_b: str) -> bool:
        """Return ``True`` if a connection already links the two zones."""
        return frozenset((zone_a, zone_b)) in self._conn_keys

    def neighbours(self, name: str) -> list[str]:
        """Return the names of zones directly connected to ``name``."""
        return self.adjacency.get(name, [])
