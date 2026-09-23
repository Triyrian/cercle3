"""Recherche de chemins dans le réseau Fly-in.

Fournit l'algorithme de Dijkstra sur le graphe pondéré des zones (coût =
``move_cost`` de la zone d'arrivée, zones ``blocked`` ignorées, zones
``priority`` gagnant les égalités) ainsi que :func:`find_paths`, qui en
extrait plusieurs chemins pour l'ordonnanceur en relançant Dijkstra avec
les zones arrivées à saturation bannies.
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
    """Renvoie le chemin le moins coûteux de ``start`` à ``end``.

    Les poids sont comparés par couples ``(cout, malus)`` : d'abord le
    coût total en tours, puis le nombre de zones non-priority
    traversées. Une zone ``priority`` gagne donc toutes les égalités de
    coût, comme le demande le sujet, sans jamais rallonger un chemin.

    Args:
        network: La carte à parcourir.
        start: Nom de la zone de départ.
        end: Nom de la zone d'arrivée.
        banned: Zones interdites (traitées comme bloquées).

    Returns:
        La liste des noms de zones de ``start`` à ``end`` (inclus), ou
        ``None`` si aucun chemin n'existe.
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
    """Renvoie plusieurs chemins de ``start`` à ``end``, du moins cher au plus.

    Relance :func:`dijkstra` en boucle ; après chaque chemin trouvé, ses
    zones intérieures sont comptées, et une zone n'est bannie qu'une fois
    son ``max_drones`` atteint. Deux chemins peuvent donc se recouvrir
    tant que les zones partagées ont la capacité de les porter. S'arrête
    quand plus aucun chemin nouveau n'existe, ou quand un lien direct
    start-end ne laisse rien à saturer.

    Args:
        network: La carte à parcourir.
        start: Nom de la zone de départ.
        end: Nom de la zone d'arrivée.

    Returns:
        La liste des chemins, le moins coûteux d'abord (peut être vide).
    """
    paths: list[list[str]] = []
    used: dict[str, int] = {}
    seen: set[tuple[str, ...]] = set()
    while True:
        banned = frozenset(
            name for name, count in used.items()
            if count >= network.zones[name].max_drones
        )
        path = dijkstra(network, start, end, banned)
        if path is None or tuple(path) in seen:
            break
        seen.add(tuple(path))
        paths.append(path)
        interior = path[1:-1]
        if not interior:
            break  # lien direct start-end : rien a saturer
        for name in interior:
            used[name] = used.get(name, 0) + 1
    return paths


def main() -> int:
    """Analyse une carte et affiche les chemins trouvés du départ au but."""
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
