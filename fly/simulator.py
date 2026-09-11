"""Moteur de simulation tour par tour de Fly-in.

Le :class:`Simulator` porte l'état *dynamique* d'une exécution (où se
trouve chaque drone, à quel point chaque zone est pleine) tandis que
:class:`~network.Network` reste une description purement statique. À
chaque tour, il décide quels drones avancent, respecte les capacités des
zones et des liens, gère les déplacements restreints en 2 tours, et
enregistre les mouvements au format de sortie du sujet.
"""

from typing import NamedTuple

from drone import Drone
from network import Connection, Network, ZoneType
from path import find_paths


class DroneState(NamedTuple):
    """Position affichable d'un drone à un instant de la simulation.

    Attributes:
        zone: La zone occupée par le drone, ou sa zone de départ tant
            que ``target`` est renseigné.
        target: Zone de destination pendant un vol vers une zone
            restreinte, ``None`` quand le drone est posé dans ``zone``.
    """

    zone: str
    target: str | None


class Simulator:
    """Conduit les drones du hub de départ au hub d'arrivée, tour par tour.

    Attributes:
        network: La carte statique.
        drones: Tous les drones à acheminer.
        occupancy: Nombre de drones présents dans chaque zone (une place
            en zone restreinte est réservée dès qu'un drone s'engage sur
            le lien qui y mène).
        log: Une liste de mouvements par tour écoulé.
        snapshots: Un instantané des positions par tour, en commençant
            par l'état initial (avant tout mouvement) à l'index 0, d'où
            ``len(snapshots) == len(log) + 1``.
    """

    def __init__(self, network: Network) -> None:
        """Crée le simulateur et son état dynamique initial."""
        self.network = network
        self.drones: list[Drone] = [
            Drone(i) for i in range(1, network.nb_drones + 1)
        ]
        self.occupancy: dict[str, int] = {name: 0 for name in network.zones}
        if network.start is not None:
            self.occupancy[network.start] = network.nb_drones
        self.log: list[list[str]] = []
        self.snapshots: list[dict[int, DroneState]] = []
        self._links: dict[frozenset[str], Connection] = {
            conn.key: conn for conn in network.connections
        }

    @property
    def turn(self) -> int:
        """Renvoie le nombre de tours de simulation écoulés."""
        return len(self.log)

    # ------------------------------------------------------------------
    # Etape 1 - routage : donner un chemin a chaque drone
    # ------------------------------------------------------------------
    def assign_paths(self) -> None:
        """Cherche les chemins candidats et y répartit les drones.

        Raises:
            RuntimeError: Si le hub d'arrivée est inatteignable.
        """
        assert self.network.start is not None
        assert self.network.end is not None
        paths = find_paths(
            self.network, self.network.start, self.network.end
        )
        if not paths:
            raise RuntimeError("no path from start to end")
        self._distribute(paths)

    def _distribute(self, paths: list[list[str]]) -> None:
        """Répartit les drones sur ``paths`` pour avancer la dernière arrivée.

        Équilibrage glouton : un chemin de coût ``L`` portant ``k``
        drones se termine vers le tour ``L + k - 1``, donc chaque drone
        est affecté au chemin dont ``cout + drones_deja_dessus`` est le
        plus petit.

        Args:
            paths: Les chemins candidats, du hub de départ à celui
                d'arrivée.
        """
        # eta[i] = tour d'arrivee du prochain drone place sur paths[i]
        eta = [self._path_cost(path) for path in paths]
        for drone in self.drones:
            best = eta.index(min(eta))
            drone.path = list(paths[best])
            eta[best] += 1

    def _path_cost(self, path: list[str]) -> int:
        """Renvoie le coût total en tours de ``path`` (départ exclu)."""
        return sum(
            self.network.zones[name].move_cost for name in path[1:]
        )

    # ------------------------------------------------------------------
    # Etape 2 - le moteur de tours
    # ------------------------------------------------------------------
    def resolve_turn(self) -> list[str]:
        """Calcule et applique tous les mouvements du tour courant.

        Ordre des opérations :
            1. La liste de travail des drones posés est construite en
               premier, ainsi un drone qui atterrit ce tour-ci ne peut
               pas bouger en plus.
            2. Les drones en vol vers une zone restreinte atterrissent
               (leur arrivée est obligatoire ; la place a été réservée
               au départ).
            3. Les drones posés sont traités du plus proche du but au
               plus loin, ainsi une zone libérée par un partant peut
               être réutilisée dans le même tour par celui de derrière.
               Un mouvement n'est accordé que si le lien a encore de la
               capacité ce tour-ci et si la zone visée a une place.

        Returns:
            Les mouvements effectués pendant ce tour.
        """
        moves: list[str] = []
        link_used: dict[frozenset[str], int] = {}

        active = [
            d for d in self.drones if not d.delivered and not d.in_transit
        ]
        active.sort(key=lambda d: d.remaining_steps)

        for drone in self.drones:
            if drone.in_transit:
                moves.append(self._land(drone))

        for drone in active:
            move = self._try_move(drone, link_used)
            if move is not None:
                moves.append(move)
        return moves

    def _land(self, drone: Drone) -> str:
        """Termine un déplacement restreint de 2 tours : pose le drone.

        Args:
            drone: Un drone actuellement en vol sur un lien.

        Returns:
            Le mouvement au format ``D<id>-<zone>``.
        """
        target = drone.land()
        if target == self.network.end:
            drone.delivered = True
        return f"{drone.label}-{target}"

    def _try_move(
        self, drone: Drone, link_used: dict[frozenset[str], int]
    ) -> str | None:
        """Tente d'avancer ``drone`` d'une étape ; le fait attendre sinon.

        Args:
            drone: Un drone posé et non encore livré.
            link_used: Nombre de passages par lien pour le tour courant.

        Returns:
            Le mouvement effectué, ou ``None`` si le drone attend.
        """
        position = drone.position
        target = drone.next_zone()
        if position is None or target is None:
            return None
        key = frozenset((position, target))
        conn = self._links[key]
        used = link_used.get(key, 0)
        if used >= conn.max_link_capacity:
            return None
        zone = self.network.zones[target]
        if (target != self.network.end
                and self.occupancy[target] >= zone.max_drones):
            return None
        link_used[key] = used + 1
        self.occupancy[position] -= 1
        self.occupancy[target] += 1
        if zone.zone_type is ZoneType.RESTRICTED:
            drone.transit_target = target
            return f"{drone.label}-{conn.zone_a}-{conn.zone_b}"
        drone.advance()
        if target == self.network.end:
            drone.delivered = True
        return f"{drone.label}-{target}"

    # ------------------------------------------------------------------
    # Etape 3 - pilotage + sortie
    # ------------------------------------------------------------------
    def is_finished(self) -> bool:
        """Renvoie ``True`` quand tous les drones sont arrivés au but."""
        return all(drone.delivered for drone in self.drones)

    def _snapshot(self) -> dict[int, DroneState]:
        """Capture la position affichable actuelle de chaque drone."""
        states: dict[int, DroneState] = {}
        for drone in self.drones:
            assert drone.position is not None
            states[drone.id] = DroneState(
                drone.position, drone.transit_target
            )
        return states

    def run(self, max_turns: int = 10_000) -> list[list[str]]:
        """Joue toute la simulation et renvoie le journal des mouvements.

        Args:
            max_turns: Garde-fou contre les boucles infinies.

        Returns:
            Le journal complet (une liste interne par tour).

        Raises:
            RuntimeError: Si aucun drone ne peut bouger (blocage) ou si
                la borne est dépassée.
        """
        self.assign_paths()
        self.snapshots.append(self._snapshot())
        while not self.is_finished():
            if self.turn >= max_turns:
                raise RuntimeError("max turn count exceeded")
            moves = self.resolve_turn()
            if not moves:
                raise RuntimeError("deadlock: no drone can move")
            self.log.append(moves)
            self.snapshots.append(self._snapshot())
        return self.log

    def format_output(self) -> str:
        """Rend le journal au format une-ligne-par-tour du sujet."""
        return "\n".join(" ".join(moves) for moves in self.log)
