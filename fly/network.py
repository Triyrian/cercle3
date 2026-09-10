"""Modèle de données du réseau de zones de Fly-in.

Définit les types de zone, les zones elles-mêmes, les connexions entre
elles, et le réseau qui agrège le tout en un graphe interrogeable.
"""

from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    """Type de déplacement d'une zone, qui fixe son coût d'entrée."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def move_cost(self) -> int:
        """Renvoie le nombre de tours nécessaires pour entrer ici."""
        return 2 if self is ZoneType.RESTRICTED else 1

    @property
    def is_passable(self) -> bool:
        """Renvoie ``True`` si un drone peut entrer dans cette zone."""
        return self is not ZoneType.BLOCKED


@dataclass
class Zone:
    """Une zone (nœud) du réseau."""

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1

    @property
    def move_cost(self) -> int:
        """Renvoie le coût en tours pour entrer dans cette zone."""
        return self.zone_type.move_cost


@dataclass
class Connection:
    """Un lien bidirectionnel (arête) entre deux zones."""

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> frozenset[str]:
        """Renvoie une identité du lien indépendante de l'ordre."""
        return frozenset((self.zone_a, self.zone_b))


class Network:
    """La carte complète : drones, zones, connexions et adjacence."""

    def __init__(self) -> None:
        """Initialise un réseau vide."""
        self.nb_drones: int = 0
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.adjacency: dict[str, list[str]] = {}
        self.start: str | None = None
        self.end: str | None = None
        self._conn_keys: set[frozenset[str]] = set()

    def add_zone(self, zone: Zone) -> None:
        """Enregistre une zone et crée son entrée d'adjacence vide."""
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

    def add_connection(self, conn: Connection) -> None:
        """Enregistre un lien et met à jour les deux listes d'adjacence."""
        self.connections.append(conn)
        self._conn_keys.add(conn.key)
        self.adjacency[conn.zone_a].append(conn.zone_b)
        self.adjacency[conn.zone_b].append(conn.zone_a)

    def has_connection(self, zone_a: str, zone_b: str) -> bool:
        """Renvoie ``True`` si un lien relie déjà les deux zones."""
        return frozenset((zone_a, zone_b)) in self._conn_keys

    def neighbours(self, name: str) -> list[str]:
        """Renvoie les noms des zones directement reliées à ``name``."""
        return self.adjacency.get(name, [])
