"""Pathfinding for the Fly-in network.

Provides Dijkstra's shortest-path algorithm on the weighted zone graph
(cost = ``move_cost`` of the destination zone, ``blocked`` zones skipped,
``priority`` zones winning cost ties) and :func:`find_paths`, which
extracts several vertex-disjoint paths for the drone scheduler by
re-running Dijkstra with used zones banned.
"""

import sys

from network import Network, ZoneType
from parsing import ParseError, Parser


def dijkstra(
    network: Network,
    start: str,
    end: str,
    banned: frozenset[str] = frozenset(),
) -> list[str] | None:
    """Return the cheapest path from ``start`` to ``end``.

    Path weights are compared as ``(cost, malus)`` pairs: total turn
    cost first, then the number of non-priority zones entered — so
    ``priority`` zones win every cost tie, as the subject requires
    ("should be prioritized in pathfinding"), without ever making a
    path slower.

    Args:
        network: The map to search.
        start: Source zone name.
        end: Destination zone name.
        banned: Zones that must not be used (treated as blocked).

    Returns:
        The list of zone names from ``start`` to ``end`` (inclusive),
        or ``None`` if no path exists.
    """
    poids: dict[str, tuple[float, int]] = {
        z: (float("inf"), 0) for z in network.zones
    }
    precedent: dict[str, str | None] = {z: None for z in network.zones}
    poids[start] = (0, 0)
    definitif: set[str] = set()

    while end not in definitif:
        # sommet non traite avec poids minimal
        x = min(
            (z for z in poids if z not in definitif),
            key=lambda z: poids[z],
        )
        if poids[x][0] == float("inf"):
            return None  # pas de chemin
        definitif.add(x)

        for voisin in network.neighbours(x):
            zone = network.zones[voisin]
            if not zone.zone_type.is_passable or voisin in banned:
                continue
            cout = poids[x][0] + zone.move_cost  # cout = type de destination
            malus = poids[x][1] + (
                0 if zone.zone_type is ZoneType.PRIORITY else 1
            )
            if (cout, malus) < poids[voisin]:
                poids[voisin] = (cout, malus)
                precedent[voisin] = x

    # reconstruire le chemin
    chemin: list[str] = []
    s: str | None = end
    while s is not None:
        chemin.append(s)
        s = precedent[s]
    chemin.reverse()
    return chemin


def find_paths(network: Network, start: str, end: str) -> list[list[str]]:
    """Return vertex-disjoint paths from ``start`` to ``end``.

    Runs :func:`dijkstra` repeatedly; after each found path, its interior
    zones are banned so the next run must take a different route. Stops
    when no further path exists, or when a direct start-end link leaves
    nothing to ban.

    Args:
        network: The map to search.
        start: Source zone name.
        end: Destination zone name.

    Returns:
        A list of paths, cheapest first (possibly empty).
    """
    paths: list[list[str]] = []
    banned: frozenset[str] = frozenset()
    while True:
        path = dijkstra(network, start, end, banned)
        if path is None:
            break
        paths.append(path)
        interior = path[1:-1]
        if not interior:
            break  # lien direct start-end : rien a bannir
        banned |= frozenset(interior)
    return paths


def main() -> int:
    """Parse a map file and print the shortest path start to end."""
    if len(sys.argv) != 2:
        print("usage: python path.py <map_file>", file=sys.stderr)
        return 1
    try:
        network = Parser().parse_file(sys.argv[1])
    except (ParseError, FileNotFoundError, OSError) as err:
        print(err, file=sys.stderr)
        return 1
    assert network.start is not None and network.end is not None
    for path in find_paths(network, network.start, network.end):
        print(" -> ".join(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
