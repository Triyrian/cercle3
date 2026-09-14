*This project has been created as part of the 42 curriculum by vtriyadi.*

# Fly-in

A turn-based, multi-drone routing simulator built for the 42 **Fly-in** project: route a whole fleet of drones from a start hub to an end hub across a graph of zones, while respecting movement costs, zone/connection capacity limits, and collision-free turn scheduling — with a graphical replay of the whole thing.

## Description

Given a small text-based map (zones, coordinates, zone types, connections, capacities) and a number of drones, the program:

1. **Parse** the map into a strict, validated graph.
2. **Route** every drone from the unique `start` hub to the unique `end` hub.
3. **Schedule** all drones turn by turn — several drones can move at once, but a zone or a connection can only hold as many drones as its declared capacity, and a move into a `restricted` zone takes two turns during which the drone cannot bail out or wait.
4. **Report** the result as a turn-by-turn move log, and optionally **replay it visually**.

Everything is written in Python 3.10+, fully type-hinted, and entirely hand-rolled: no graph library (`networkx`, `graphlib`, …) is used — the adjacency-list graph, Dijkstra's algorithm, and the turn-based scheduler are all code-implemented.

## Instructions

### Installation

Requires Python 3.10+ and `pip`.

```sh
make install
```

This installs the project's only dependencies: `flake8`, `mypy` (linting) and `pygame` (visualization).

### Execution

```sh
make run                                   # runs the default map (maps/easy/01_linear_path.txt)
make run MAP=maps/hard/02_capacity_hell.txt  # runs a specific map
make visual MAP=maps/easy/01_linear_path.txt  # runs it and opens the graphical replay
```

Or call the entry point directly:

```sh
python3 fly.py <map_file>            # prints the turn-by-turn move log
python3 fly.py <map_file> --visual   # same, then opens the graphical replay window
```

Other Makefile targets:

| Target | Purpose |
|---|---|
| `make debug` | Runs the simulation under `pdb` |
| `make lint` | `flake8 .` + `mypy .` with the mandatory flags |
| `make lint-strict` | `flake8 .` + `mypy . --strict` |
| `make clean` | Removes `__pycache__`, `.mypy_cache`, `*.pyc` |

### Usage example

```
$ python3 fly.py maps/easy/02_simple_fork.txt
D1-junction D2-junction
D1-path_a D3-junction
D1-goal D2-path_a D4-junction
D2-goal D3-path_a
D3-goal D4-path_a
D4-goal

turns: 6
```

In the graphical replay (`--visual`), use the on-screen **`< Prev` / `Next >`** buttons, the arrow keys, `Space`, `Home` or `End` to step through the exact same run turn by turn; drag with the mouse to pan and scroll to zoom.

## Algorithm & Implementation Strategy

The pipeline is split into four independent, single-purpose modules, wired together by `fly.py`:

- **`network.py`** — the static data model: `ZoneType` (`normal`/`priority` cost 1, `restricted` cost 2, `blocked` impassable), `Zone`, `Connection` (identified by an order-independent `frozenset` key, so `a-b` and `b-a` collide correctly), and `Network`, a hand-rolled adjacency-list graph.
- **`parsing.py`** — a line-by-line `Parser` that validates the map format strictly against the subject: unique `start_hub`/`end_hub`, no duplicate zone names or connections, only forward-referenced connections, valid zone types and positive capacities, and a located `line N: <cause>` `ParseError` on any violation.
- **`path.py`** — classic **Dijkstra's algorithm** over the zone graph, weighted by each destination zone's `move_cost` and skipping `blocked` zones; path weights are compared as `(cost, non-priority steps)` pairs so `priority` zones win every cost tie, as the subject requires, without ever making a path slower. `find_paths()` reruns it repeatedly, banning the interior zones of each path already found, to produce several **vertex-disjoint routes** instead of a single corridor every drone would have to squeeze through.
- **`simulator.py`** — the turn engine, and the actual core of the project:
  - **Routing**: drones are greedily distributed across the disjoint paths found above, each new drone going to whichever path minimizes its projected finish turn (`path cost + drones already queued on it`).
  - **Scheduling**: each turn, drones already in transit toward a `restricted` zone land unconditionally (their slot was reserved the turn they departed — they can never be stuck waiting mid-flight, matching the subject's rule). Settled drones are then processed **nearest-to-goal first**, so a zone freed by a drone leaving it can be reused by the drone behind it within that very same turn. A move is only granted if the destination zone still has a free `max_drones` slot and the connection hasn't exceeded its `max_link_capacity` this turn.
  - **Deadlock handling**: *reactive*, not preventive — if a turn produces zero possible moves, the simulator raises rather than silently looping forever. Proactively avoiding gridlocks (e.g. via lookahead or replanning) is the main identified area for further improvement.

**Complexity**: each Dijkstra run is `O(V²)` (a linear scan for the minimum-weight unvisited zone — fine at this map scale, a binary-heap priority queue would bring it down to `O(E log V)` on larger graphs); the turn engine is `O(turns × drones)`. Nothing is cached across runs since each map is only solved once per invocation.

**Measured performance** against the maps and targets from the subject:

| Map | Drones | Turns | Target | Result |
|---|---|---|---|---|
| easy/01_linear_path | 2 | 4 | ≤ 6 | ✅ |
| easy/02_simple_fork | 4 | 6 | ≤ 8 | ✅ |
| easy/03_basic_capacity | 4 | 4 | ≤ 6 | ✅ |
| medium/01_dead_end_trap | 5 | 8 | ≤ 12 | ✅ |
| medium/02_circular_loop | 6 | 15 | ≤ 15 | ✅ |
| medium/03_priority_puzzle | 5 | 8 | ≤ 12 | ✅ |
| hard/01_maze_nightmare | 8 | 13 | ≤ 30 | ✅ |
| hard/02_capacity_hell | 12 | 16 | ≤ 35 | ✅ |
| hard/03_ultimate_challenge | 15 | 26 | ≤ 45 | ✅ |
| challenger/01_the_impossible_dream (bonus) | 25 | 67 | 45 (record) | not beaten |

Every mandatory benchmark is met or beaten; the optional challenger map is solved but does not beat the reference record.

## Visual Representation

`visual.py` is a **secondary implementation**: it is not part of the routing logic itself, but a `pygame`-based graphical interface used to *visualize* and *check* that the main program (parser, pathfinding, turn engine) behaves correctly. Unlike the rest of the project, this module was written **almost entirely by AI** (see *AI usage* below); I reviewed and tested it, but I did not author it. It gives two layers of feedback:

- **The static map**: every zone drawn as a circle colored by its type (or by its own `color` metadata when set), the `start` and `end` hubs outlined in green/red, connections drawn as lines, and a free-form camera (click-drag to pan, scroll wheel to zoom, anchored under the cursor).
- **The live simulation replay**: each drone is drawn as a small numbered marker at its zone for the selected turn — or halfway along a connection when it's mid-flight toward a `restricted` zone — with drones sharing a zone spread out in a small circle so none are hidden behind another. A HUD in the top-left shows the current turn, how many drones have been delivered, and that turn's exact move list. **`< Prev` / `Next >`** buttons (also bound to the arrow keys, `Space`, `Home`, `End`) let you step through the run one turn at a time.

This turns the visualization from a static picture of the map into an actual debugging and understanding tool: you can watch exactly which drone waits for which zone to free up, see the two-turn restricted transit happen, and confirm capacity limits are never exceeded — all by stepping through the same log that `format_output()` prints to the terminal.

## Resources

### Documentation and references
- Terminale Generale NSI
- Dijkstra, E. W. (1959), *A Note on Two Problems in Connexion with Graphs* — the algorithm behind `path.py`.
- *Introduction to Algorithms* (Cormen, Leiserson, Rivest, Stein) — reference for graph representations and shortest-path/turn-scheduling reasoning.
- [pygame documentation](https://www.pygame.org/docs/) — used for the graphical interface.
- [flake8](https://flake8.pycqa.org/) and [mypy](https://mypy.readthedocs.io/) documentation — used for linting and static type checking.
- Previous 42 project, friends and pairs

### AI usage

AI was used during development as a development assistant, not as a code-generation shortcut — every suggestion below was reviewed, tested, and understood before being kept, it was used for:

- **Codebase auditing**: reading the whole project file by file against the official subject PDF to produce an accurate, line-cited gap analysis (what's implemented, what's partial, what's missing) — used to prioritize remaining work rather than guess at it.
- **Writing `visual.py` almost entirely**: the graphical replay module (map rendering, camera pan/zoom, per-turn drone rendering, HUD, `Prev`/`Next` navigation) is AI-generated code. It is a secondary tool whose only purpose is to visualize and sanity-check the main program; I reviewed it, ran it on every sample map, and checked headless screenshots (drone positions, mid-flight transit, delivered state), but I did not write it myself. The core of the project — `network.py`, `parsing.py`, `path.py`, `drone.py`, `simulator.py`, `fly.py` — is my own work, with AI used only for review, refactoring suggestions and bug-hunting as described in the other bullets.
- **Bug fixing**: catching and fixing a pre-existing `mypy` type-annotation error (`pygame.event` → `pygame.event.Event`).
- **Linting/type-checking support**: running `flake8`/`mypy` after each change and fixing the reported issues.
- **Drafting this README**, cross-checked against the subject's Chapter VIII requirements and the actual code/benchmarks.

### Project Structure

| File | Role |
|---|---|
| `network.py` | Static data model: `ZoneType`, `Zone`, `Connection`, `Network` graph |
| `parsing.py` | Map file parser and validation (`Parser`, `ParseError`) |
| `path.py` | Dijkstra's algorithm and disjoint multi-path search |
| `drone.py` | `Drone` state (position, path, in-transit status) |
| `simulator.py` | Turn-by-turn scheduling engine and output formatting |
| `visual.py` | `pygame` graphical replay — secondary tool, written almost entirely by AI (see *AI usage*) |
| `fly.py` | CLI entry point wiring the pipeline together |
| `Makefile` | `install` / `run` / `visual` / `debug` / `lint` / `lint-strict` / `clean` |
| `maps/` | Sample maps (easy / medium / hard / challenger tiers) |
