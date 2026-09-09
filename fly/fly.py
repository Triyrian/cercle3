"""Fly-in entry point.

Wires the pipeline together: parse a map file into a
:class:`~network.Network`, run the :class:`~simulator.Simulator`, print the
turn-by-turn output, and optionally launch the pygame visualisation.

Usage:
    python fly.py <map_file> [--visual]
"""

import sys

from parsing import ParseError, Parser
from simulator import Simulator

USAGE = "usage: python fly.py <map_file> [--visual]"


def main() -> int:
    """Parse arguments, run the simulation and print the result."""
    args = sys.argv[1:]
    if not args or len(args) > 2:
        print(USAGE, file=sys.stderr)
        return 1
    if len(args) == 2 and args[1] != "--visual":
        print(USAGE, file=sys.stderr)
        return 1
    map_file = args[0]
    want_visual = len(args) == 2

    try:
        network = Parser().parse_file(map_file)
    except (ParseError, FileNotFoundError, OSError) as error:
        print(error, file=sys.stderr)
        return 1

    simulator = Simulator(network)
    try:
        simulator.run()
    except RuntimeError as error:
        print(f"simulation error: {error}", file=sys.stderr)
        return 1

    print(simulator.format_output())
    print(f"\nturns: {simulator.turn}")

    if want_visual:
        try:
            from visual import Visualization
            Visualization(network, simulator.snapshots, simulator.log).run()
        except (ImportError, RuntimeError) as error:
            print(f"visualization error: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
