"""État d'un drone pour la simulation Fly-in.

Un :class:`Drone` n'est qu'un enregistrement de sa progression le long du
chemin qui lui a été assigné ; toute décision sur le *moment* où il bouge
appartient au :class:`~simulator.Simulator`.
"""


class Drone:
    """Un drone qui parcourt le chemin qui lui a été assigné.

    Attributes:
        id: Identifiant unique (affiché ``D<id>`` dans la sortie).
        path: Liste ordonnée des zones, du hub de départ à celui
            d'arrivée.
        step_index: Index dans :attr:`path` de la zone occupée.
        transit_target: Nom de la zone restreinte en cours d'entrée
            pendant que le drone est sur un lien, ``None`` s'il est posé.
        delivered: ``True`` une fois le hub d'arrivée atteint.
    """

    def __init__(self, drone_id: int) -> None:
        """Crée un drone sans chemin (assigné plus tard)."""
        self.id = drone_id
        self.path: list[str] = []
        self.step_index: int = 0
        self.transit_target: str | None = None
        self.delivered: bool = False

    @property
    def label(self) -> str:
        """Renvoie l'étiquette de sortie du drone (ex. ``D1``)."""
        return f"D{self.id}"

    @property
    def position(self) -> str | None:
        """Renvoie la zone occupée, ou ``None`` si aucun chemin."""
        if not self.path:
            return None
        return self.path[self.step_index]

    @property
    def in_transit(self) -> bool:
        """Renvoie ``True`` si le drone vole vers une zone restreinte."""
        return self.transit_target is not None

    @property
    def remaining_steps(self) -> int:
        """Renvoie le nombre d'étapes restantes avant le but."""
        return len(self.path) - self.step_index

    def next_zone(self) -> str | None:
        """Renvoie la zone suivante du chemin, ou ``None`` à la fin."""
        if not self.path or self.step_index + 1 >= len(self.path):
            return None
        return self.path[self.step_index + 1]

    def advance(self) -> None:
        """Avance le drone d'une étape sur son chemin."""
        if self.step_index + 1 < len(self.path):
            self.step_index += 1

    def land(self) -> str:
        """Termine un déplacement restreint de 2 tours et pose le drone.

        Returns:
            Le nom de la zone dans laquelle le drone atterrit.
        """
        assert self.transit_target is not None
        target = self.transit_target
        self.advance()
        self.transit_target = None
        return target
