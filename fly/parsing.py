"""Parser for the Fly-in drone routing map format.

Reads a map file, validates it against the subject rules,
and builds an in-memory :class:`~network.Network`.

Each line is routed to a handler via a dispatch table keyed on the
line prefix (``nb_drones:``, ``start_hub:``, ``end_hub:``, ``hub:``,
``connection:``). Any syntax or semantic error stops parsing immediately
and reports the offending line and cause.
"""

import sys
from typing import Callable

from network import Connection, Network, Zone, ZoneType


class ParseError(Exception):
    """Raised when a map file violates the expected format or rules.

    Attributes:
        line_no: 1-based line number where the error was detected
            (``0`` means a global/end-of-file error).
    """

    def __init__(self, line_no: int, message: str) -> None:
        """Build the error with a human-readable, located message."""
        where = "end of file" if line_no == 0 else f"line {line_no}"
        super().__init__(f"[parse error] {where}: {message}")
        self.line_no = line_no


class Parser:
    """Parser that turns a map file into a :class:`~network.Network`."""

    ZONE_KEYS = {"zone", "color", "max_drones"}
    CONNECTION_KEYS = {"max_link_capacity"}

    def __init__(self) -> None:
        """Initialise the parser with its line dispatch table."""
        self.network = Network()
        self._nb_drones_set = False
        self._dispatch: dict[str, Callable[[str, int], None]] = {
            "nb_drones": self._handle_nb_drones,
            "start_hub": self._handle_start_hub,
            "end_hub":   self._handle_end_hub,
            "hub":       self._handle_hub,
            "connection": self._handle_connection,
        }

    def parse_file(self, path: str) -> Network:
        """Parse a map file and return the validated network.

        Args:
            path: Path to the map file.

        Returns:
            The fully built and validated :class:`~network.Network`.

        Raises:
            ParseError: If the file violates the format or rules.
            FileNotFoundError: If the file does not exist.
        """
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line_no, raw in enumerate(handle, start=1):
                    self._parse_line(raw, line_no)
        except UnicodeDecodeError as error:
            raise ParseError(0, f"file is not valid UTF-8 ({error})") from None
        self._final_validation()
        return self.network

    def _parse_line(self, raw: str, line_no: int) -> None:
        """Strip, skip comments, then dispatch a single line."""
        line = raw.strip()
        if not line or line.startswith("#"):
            return
        if ":" not in line:
            raise ParseError(line_no, f"missing ':' separator in {line!r}")
        prefix, rest = line.split(":", 1)
        handler = self._dispatch.get(prefix.strip())
        if handler is None:
            raise ParseError(line_no, f"unknown line type {prefix.strip()!r}")
        handler(rest.strip(), line_no)

    def _handle_nb_drones(self, rest: str, line_no: int) -> None:
        """Handle the mandatory ``nb_drones:`` directive."""
        if self._nb_drones_set:
            raise ParseError(line_no, "nb_drones defined more than once")
        if self.network.zones or self.network.connections:
            raise ParseError(line_no, "nb_drones must be the first directive")
        self.network.nb_drones = self._positive_int(rest, line_no, "nb_drones")
        self._nb_drones_set = True

    def _handle_start_hub(self, rest: str, line_no: int) -> None:
        """Handle a ``start_hub:`` zone line."""
        self._add_zone(rest, line_no, is_start=True, is_end=False)

    def _handle_end_hub(self, rest: str, line_no: int) -> None:
        """Handle an ``end_hub:`` zone line."""
        self._add_zone(rest, line_no, is_start=False, is_end=True)

    def _handle_hub(self, rest: str, line_no: int) -> None:
        """Handle a regular ``hub:`` zone line."""
        self._add_zone(rest, line_no, is_start=False, is_end=False)

    def _add_zone(
        self, rest: str, line_no: int, is_start: bool, is_end: bool
    ) -> None:
        """Parse a zone body, validate it and add it to the network."""
        if not self._nb_drones_set:
            raise ParseError(line_no, "nb_drones must be defined first")
        body, meta = self._split_meta(rest, line_no)
        parts = body.split()
        if len(parts) != 3:
            raise ParseError(
                line_no, "expected '<name> <x> <y>' before metadata"
            )
        name, raw_x, raw_y = parts
        self._check_name(name, line_no)
        if name in self.network.zones:
            raise ParseError(line_no, f"duplicate zone name {name!r}")
        x = self._integer(raw_x, line_no, "x coordinate")
        y = self._integer(raw_y, line_no, "y coordinate")
        self._check_unknown_keys(meta, self.ZONE_KEYS, line_no)
        zone = Zone(
            name, x, y,
            zone_type=self._zone_type(meta, line_no),
            color=meta.get("color"),
            max_drones=self._zone_capacity(meta, line_no),
        )
        self.network.add_zone(zone)
        if is_start:
            self._set_unique_start(name, line_no)
        if is_end:
            self._set_unique_end(name, line_no)

    def _set_unique_start(self, name: str, line_no: int) -> None:
        """Record the start hub, rejecting a second definition."""
        if self.network.start is not None:
            raise ParseError(line_no, "more than one start_hub defined")
        self.network.start = name

    def _set_unique_end(self, name: str, line_no: int) -> None:
        """Record the end hub, rejecting a second definition."""
        if self.network.end is not None:
            raise ParseError(line_no, "more than one end_hub defined")
        self.network.end = name

    def _handle_connection(self, rest: str, line_no: int) -> None:
        """Parse a ``connection:`` line and add the edge."""
        if not self._nb_drones_set:
            raise ParseError(line_no, "nb_drones must be defined first")
        body, meta = self._split_meta(rest, line_no)
        names = body.split("-")
        if len(names) != 2 or not names[0].strip() or not names[1].strip():
            raise ParseError(line_no, "connection must be '<zone1>-<zone2>'")
        zone_a, zone_b = names[0].strip(), names[1].strip()
        for zone_name in (zone_a, zone_b):
            if zone_name not in self.network.zones:
                raise ParseError(line_no, f"unknown zone {zone_name!r}")
        if zone_a == zone_b:
            raise ParseError(line_no, "a zone cannot connect to itself")
        if self.network.has_connection(zone_a, zone_b):
            raise ParseError(
                line_no, f"duplicate connection {zone_a}-{zone_b}"
            )
        self._check_unknown_keys(meta, self.CONNECTION_KEYS, line_no)
        cap = self._link_capacity(meta, line_no)
        self.network.add_connection(Connection(zone_a, zone_b, cap))

    def _split_meta(
        self, body: str, line_no: int
    ) -> tuple[str, dict[str, str]]:
        """Split a body into its main text and ``[key=value ...]`` map."""
        if "[" not in body and "]" not in body:
            return body.strip(), {}
        if body.count("[") != 1 or body.count("]") != 1:
            raise ParseError(line_no, "malformed metadata brackets")
        open_i = body.index("[")
        close_i = body.index("]")
        if close_i < open_i or not body.rstrip().endswith("]"):
            raise ParseError(line_no, "malformed metadata brackets")
        main = body[:open_i].strip()
        inner = body[open_i + 1:close_i].strip()
        meta: dict[str, str] = {}
        for token in inner.split():
            if token.count("=") != 1:
                raise ParseError(line_no, f"invalid metadata {token!r}")
            key, value = token.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key or not value:
                raise ParseError(line_no, f"invalid metadata {token!r}")
            if key in meta:
                raise ParseError(line_no, f"duplicate metadata key {key!r}")
            meta[key] = value
        return main, meta

    def _zone_type(self, meta: dict[str, str], line_no: int) -> ZoneType:
        """Resolve the ``zone=`` metadata into a :class:`~network.ZoneType`."""
        raw = meta.get("zone", "normal")
        try:
            return ZoneType(raw)
        except ValueError:
            raise ParseError(line_no, f"invalid zone type {raw!r}") from None

    def _zone_capacity(self, meta: dict[str, str], line_no: int) -> int:
        """Resolve the ``max_drones=`` metadata (default ``1``)."""
        if "max_drones" not in meta:
            return 1
        return self._positive_int(meta["max_drones"], line_no, "max_drones")

    def _link_capacity(self, meta: dict[str, str], line_no: int) -> int:
        """Resolve the ``max_link_capacity=`` metadata (default ``1``)."""
        if "max_link_capacity" not in meta:
            return 1
        return self._positive_int(
            meta["max_link_capacity"], line_no, "max_link_capacity"
        )

    def _check_unknown_keys(
        self, meta: dict[str, str], allowed: set[str], line_no: int
    ) -> None:
        """Raise if metadata contains a key outside ``allowed``."""
        for key in meta:
            if key not in allowed:
                raise ParseError(line_no, f"unknown metadata key {key!r}")

    def _check_name(self, name: str, line_no: int) -> None:
        """Validate a zone name (no dashes, no empty name)."""
        if not name:
            raise ParseError(line_no, "empty zone name")
        if "-" in name:
            raise ParseError(line_no, f"zone name {name!r} cannot contain '-'")

    def _integer(self, value: str, line_no: int, field: str) -> int:
        """Parse an integer, raising a located error on failure."""
        try:
            return int(value)
        except ValueError:
            raise ParseError(
                line_no, f"{field} must be an integer, got {value!r}"
            ) from None

    def _positive_int(self, value: str, line_no: int, field: str) -> int:
        """Parse a strictly positive integer."""
        number = self._integer(value, line_no, field)
        if number <= 0:
            raise ParseError(
                line_no, f"{field} must be positive, got {number}"
            )
        return number

    def _final_validation(self) -> None:
        """Run global checks once every line has been parsed."""
        if not self._nb_drones_set:
            raise ParseError(0, "missing 'nb_drones' directive")
        if self.network.start is None:
            raise ParseError(0, "missing start_hub")
        if self.network.end is None:
            raise ParseError(0, "missing end_hub")
        for name in (self.network.start, self.network.end):
            if not self.network.zones[name].zone_type.is_passable:
                raise ParseError(0, f"hub {name!r} cannot be blocked")


def main() -> int:
    """Parse a map passed on the command line and print a summary."""
    if len(sys.argv) != 2:
        print("usage: python parsing.py <map_file>", file=sys.stderr)
        return 1
    try:
        network = Parser().parse_file(sys.argv[1])
    except (ParseError, FileNotFoundError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"drones      : {network.nb_drones}")
    print(f"start / end : {network.start} -> {network.end}")
    print(f"zones       : {len(network.zones)}")
    print(f"connections : {len(network.connections)}")
    for zone in network.zones.values():
        cap = str(zone.max_drones)
        print(
            f"-{zone.name:<18} {zone.zone_type.value:<10} "
            f"cost={zone.move_cost} cap={cap}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
