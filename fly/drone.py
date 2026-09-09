"""Drone state for the Fly-in simulation.

A :class:`Drone` is a passive record of one drone's progress along its
pre-assigned path; every decision about *when* it moves belongs to the
:class:`~simulator.Simulator`.
"""


class Drone:
    """A single drone travelling along a pre-assigned path.

    Attributes:
        id: Unique identifier (rendered as ``D<id>`` in the output).
        path: Ordered list of zone names, from start hub to end hub.
        step_index: Index in :attr:`path` of the zone currently occupied.
        transit_target: Name of the restricted zone being entered while
            the drone is on a connection, or ``None`` when settled.
        delivered: ``True`` once the drone has reached the end hub.
    """

    def __init__(self, drone_id: int) -> None:
        """Create a drone with an empty path (assigned later)."""
        self.id = drone_id
        self.path: list[str] = []
        self.step_index: int = 0
        self.transit_target: str | None = None
        self.delivered: bool = False

    @property
    def label(self) -> str:
        """Return the output label of the drone (e.g. ``D1``)."""
        return f"D{self.id}"

    @property
    def position(self) -> str | None:
        """Return the zone currently occupied, or ``None`` if unset."""
        if not self.path:
            return None
        return self.path[self.step_index]

    @property
    def in_transit(self) -> bool:
        """Return ``True`` if the drone is flying toward a restricted zone."""
        return self.transit_target is not None

    @property
    def remaining_steps(self) -> int:
        """Return how many path steps separate the drone from its goal."""
        return len(self.path) - self.step_index

    def next_zone(self) -> str | None:
        """Return the next zone on the path, or ``None`` at the end."""
        if not self.path or self.step_index + 1 >= len(self.path):
            return None
        return self.path[self.step_index + 1]

    def advance(self) -> None:
        """Move the drone one step forward along its path."""
        if self.step_index + 1 < len(self.path):
            self.step_index += 1

    def land(self) -> str:
        """Finish a 2-turn restricted move and settle in the target zone.

        Returns:
            The name of the zone the drone lands in.
        """
        assert self.transit_target is not None
        target = self.transit_target
        self.advance()
        self.transit_target = None
        return target
