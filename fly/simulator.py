"""Turn-by-turn simulation engine for Fly-in.

The :class:`Simulator` owns the *dynamic* state of a run (where each
drone is, how full each zone is) while :class:`~network.Network` stays a
pure static description. Each turn it decides which drones may advance,
respects zone and link capacities, handles 2-turn restricted moves, and
records the moves in the subject's output format.
"""

from typing import NamedTuple

from drone import Drone
from network import Connection, Network, ZoneType
from path import find_paths


class DroneState(NamedTuple):
    """Renderable position of one drone at a given turn checkpoint.

    Attributes:
        zone: The zone the drone occupies, or its departure zone while
            ``target`` is set.
        target: Destination zone while in transit toward a restricted
            zone, or ``None`` when the drone is settled in ``zone``.
    """

    zone: str
    target: str | None


class Simulator:
    """Drive drones from the start hub to the end hub, turn by turn.

    Attributes:
        network: The static map.
        drones: All drones being routed.
        occupancy: Number of drones currently in each zone (a slot in a
            restricted zone is reserved as soon as a drone enters the
            link toward it).
        log: One list of move strings per completed turn.
        snapshots: One drone-position snapshot per turn checkpoint,
            starting with the initial state (before any move) at index
            0, so ``len(snapshots) == len(log) + 1``.
    """

    def __init__(self, network: Network) -> None:
        """Create the simulator and its initial dynamic state."""
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
        """Return the number of completed simulation turns."""
        return len(self.log)

    # ------------------------------------------------------------------
    # Step 1 - routing: give every drone a path
    # ------------------------------------------------------------------
    def assign_paths(self) -> None:
        """Find candidate paths and distribute the drones across them.

        Raises:
            RuntimeError: If the end hub is unreachable.
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
        """Spread drones across ``paths`` to minimise the last arrival.

        Greedy balancing: a path of cost ``L`` carrying ``k`` drones
        finishes around turn ``L + k - 1``, so each drone is assigned to
        the path whose ``cost + drones_already_on_it`` is the smallest.

        Args:
            paths: Candidate paths, each from start hub to end hub.
        """
        costs = [self._path_cost(path) for path in paths]
        counts = [0] * len(paths)
        for drone in self.drones:
            best = min(
                range(len(paths)), key=lambda i: costs[i] + counts[i]
            )
            drone.path = list(paths[best])
            counts[best] += 1

    def _path_cost(self, path: list[str]) -> int:
        """Return the total turn cost of ``path`` (source excluded)."""
        return sum(
            self.network.zones[name].move_cost for name in path[1:]
        )

    # ------------------------------------------------------------------
    # Step 2 - the turn engine
    # ------------------------------------------------------------------
    def resolve_turn(self) -> list[str]:
        """Compute and apply every drone move for the current turn.

        Order of operations:
            1. The worklist of settled drones is built first, so a drone
               landing this turn cannot also move this turn.
            2. Drones in transit toward a restricted zone land (their
               arrival is mandatory; the slot was reserved at departure).
            3. Settled drones are processed nearest-to-goal first, so a
               zone freed by a leaving drone can be reused in the same
               turn by the drone behind it. A move is granted only if
               the link has capacity left this turn and the destination
               zone has a free slot.

        Returns:
            The move strings performed this turn.
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
        """Finish a 2-turn restricted move: settle the drone.

        Args:
            drone: A drone currently in transit on a link.

        Returns:
            The move string ``D<id>-<zone>``.
        """
        target = drone.land()
        if target == self.network.end:
            drone.delivered = True
        return f"{drone.label}-{target}"

    def _try_move(
        self, drone: Drone, link_used: dict[frozenset[str], int]
    ) -> str | None:
        """Try to advance ``drone`` by one step; make it wait otherwise.

        Args:
            drone: A settled, undelivered drone.
            link_used: Per-link move count for the current turn.

        Returns:
            The move string, or ``None`` if the drone waits this turn.
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
    # Step 3 - driver + output
    # ------------------------------------------------------------------
    def is_finished(self) -> bool:
        """Return ``True`` when every drone has reached the end hub."""
        return all(drone.delivered for drone in self.drones)

    def _snapshot(self) -> dict[int, DroneState]:
        """Capture each drone's current renderable position."""
        states: dict[int, DroneState] = {}
        for drone in self.drones:
            assert drone.position is not None
            states[drone.id] = DroneState(
                drone.position, drone.transit_target
            )
        return states

    def run(self, max_turns: int = 10_000) -> list[list[str]]:
        """Play the whole simulation and return the per-turn move log.

        Args:
            max_turns: Safety bound against infinite loops.

        Returns:
            The full move log (one inner list per turn).

        Raises:
            RuntimeError: If no drone can move (deadlock) or the bound
                is exceeded.
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
        """Render the move log in the subject's line-per-turn format."""
        return "\n".join(" ".join(moves) for moves in self.log)
