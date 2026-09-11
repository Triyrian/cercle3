"""Point d'entrée de Fly-in.

Assemble la chaîne complète : analyse un fichier de carte en
:class:`~network.Network`, lance le :class:`~simulator.Simulator`,
affiche la sortie tour par tour, et ouvre éventuellement la
visualisation pygame.
"""

import sys

from parsing import ParseError, Parser
from simulator import Simulator

USAGE = "usage: python fly.py <map_file> [--visual]"


def main() -> int:
    """Analyse les arguments, lance la simulation et affiche le bilan."""
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
