"""Pygame visualisation for Fly-in.

Draws the zone graph and replays a finished simulation turn by turn:
drones appear on their zones (or mid-link while in transit toward a
restricted zone), a HUD shows the current turn and its moves, and
``< Prev`` / ``Next >`` buttons (or the keyboard) step through the run.
"""

import math

import pygame

from network import Network, Zone, ZoneType
from simulator import DroneState

FALLBACK_COLORS: dict[ZoneType, tuple[int, int, int]] = {
    ZoneType.NORMAL: (180, 180, 180),
    ZoneType.RESTRICTED: (255, 140, 0),
    ZoneType.PRIORITY: (80, 200, 80),
    ZoneType.BLOCKED: (50, 50, 50),
}

DRONE_COLOR = (20, 60, 220)
BUTTON_COLOR = (70, 130, 220)
BUTTON_DISABLED_COLOR = (180, 180, 180)


class Visualization:
    """Interactive window showing the map and the simulation replay."""

    BASE_SCALE = 100
    ZONE_RADIUS = 10
    DRONE_RADIUS = 7
    BUTTON_SIZE = (90, 34)
    SPREAD_FACTOR = 1.6  # ring radius between stacked drones, in radii
    ZOOM_MIN = 0.1
    ZOOM_MAX = 8.0
    ZOOM_STEP = 1.1

    def __init__(
        self,
        network: Network,
        snapshots: list[dict[int, DroneState]],
        log: list[list[str]],
    ) -> None:
        """Open the window and centre the camera on ``network``."""
        self.network = network
        self.snapshots = snapshots
        self.log = log
        self.turn_index = 0

        pygame.init()
        self.screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        pygame.display.set_caption("Fly-In Visualization")
        self.font = pygame.font.SysFont(None, 20)
        self.hud_font = pygame.font.SysFont(None, 24)
        self.drone_font = pygame.font.SysFont(None, 16)

        xs = [z.x for z in network.zones.values()]
        ys = [z.y for z in network.zones.values()]
        self.min_x = min(xs)
        self.min_y = min(ys)

        # camera centred on the graph at startup
        self.cam_x: float = (max(xs) - self.min_x) * self.BASE_SCALE / 2
        self.cam_y: float = (max(ys) - self.min_y) * self.BASE_SCALE / 2
        self.zoom: float = 1.0

        self._dragging = False
        self._drag_mouse: tuple[int, int] = (0, 0)
        self._drag_cam:  tuple[float, float] = (0.0, 0.0)

        self._prev_rect = pygame.Rect(0, 0, *self.BUTTON_SIZE)
        self._next_rect = pygame.Rect(0, 0, *self.BUTTON_SIZE)

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------
    def _to_screen(self, lx: int, ly: int) -> tuple[int, int]:
        """Convert map coordinates to pixels under the current camera."""
        wx = (lx - self.min_x) * self.BASE_SCALE
        wy = (ly - self.min_y) * self.BASE_SCALE
        cx = self.screen.get_width() / 2
        cy = self.screen.get_height() / 2
        return (int((wx - self.cam_x) * self.zoom + cx),
                int((wy - self.cam_y) * self.zoom + cy))

    def _drone_radius(self) -> int:
        """Return the on-screen drone radius under the current zoom."""
        return max(4, int(self.DRONE_RADIUS * self.zoom))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _zone_color(self, zone: Zone) -> pygame.Color:
        """Return the map-declared color of ``zone``, or its type color."""
        if zone.color:
            try:
                return pygame.Color(zone.color)
            except ValueError:
                pass
        return pygame.Color(*FALLBACK_COLORS[zone.zone_type])

    def _draw_connections(self) -> None:
        """Draw every connection as a line between its two zones."""
        for conn in self.network.connections:
            za = self.network.zones[conn.zone_a]
            zb = self.network.zones[conn.zone_b]
            pygame.draw.line(
                self.screen, (120, 120, 120),
                self._to_screen(za.x, za.y),
                self._to_screen(zb.x, zb.y), 2,
            )

    def _draw_zones(self) -> None:
        """Draw every zone as a colored circle with its name below."""
        r = max(6, int(self.ZONE_RADIUS * self.zoom))
        for zone in self.network.zones.values():
            pos = self._to_screen(zone.x, zone.y)
            pygame.draw.circle(self.screen, self._zone_color(zone), pos, r)
            # thick border for start / end
            if zone.name == self.network.start:
                pygame.draw.circle(self.screen, (0, 180, 0), pos, r, 3)
            elif zone.name == self.network.end:
                pygame.draw.circle(self.screen, (200, 0, 0), pos, r, 3)
            # name label below the circle
            label = self.font.render(zone.name, True, (0, 0, 0))
            self.screen.blit(
                label, (pos[0] - label.get_width() // 2, pos[1] + r)
            )

    def _drone_screen_positions(self) -> dict[int, tuple[int, int]]:
        """Return each drone's screen position for the current turn.

        Drones sharing the exact same spot (same zone, or mid-flight on
        the same connection) are spread in a small circle so they stay
        individually visible.
        """
        snapshot = self.snapshots[self.turn_index]
        raw: dict[int, tuple[int, int]] = {}
        for drone_id, state in snapshot.items():
            za = self.network.zones[state.zone]
            if state.target is None:
                raw[drone_id] = self._to_screen(za.x, za.y)
            else:
                zb = self.network.zones[state.target]
                pa = self._to_screen(za.x, za.y)
                pb = self._to_screen(zb.x, zb.y)
                raw[drone_id] = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)

        groups: dict[tuple[int, int], list[int]] = {}
        for drone_id, pos in raw.items():
            groups.setdefault(pos, []).append(drone_id)

        ring = self._drone_radius() * self.SPREAD_FACTOR
        spread: dict[int, tuple[int, int]] = {}
        for pos, ids in groups.items():
            if len(ids) == 1:
                spread[ids[0]] = pos
                continue
            for i, drone_id in enumerate(ids):
                angle = 2 * math.pi * i / len(ids)
                spread[drone_id] = (
                    pos[0] + int(math.cos(angle) * ring),
                    pos[1] + int(math.sin(angle) * ring),
                )
        return spread

    def _draw_drones(self) -> None:
        """Draw every drone as a labelled dot at its current position."""
        r = self._drone_radius()
        for drone_id, pos in self._drone_screen_positions().items():
            pygame.draw.circle(self.screen, DRONE_COLOR, pos, r)
            pygame.draw.circle(self.screen, (255, 255, 255), pos, r, 1)
            label = self.drone_font.render(
                f"D{drone_id}", True, (255, 255, 255)
            )
            self.screen.blit(
                label,
                (pos[0] - label.get_width() // 2,
                 pos[1] - label.get_height() // 2),
            )

    def _draw_hud(self) -> None:
        """Draw the turn counter, delivery count and current moves."""
        total = len(self.snapshots) - 1
        snapshot = self.snapshots[self.turn_index]
        delivered = sum(
            1 for state in snapshot.values()
            if state.zone == self.network.end and state.target is None
        )
        lines = [
            f"Turn {self.turn_index} / {total}",
            f"Delivered: {delivered} / {len(snapshot)}",
        ]
        if 0 < self.turn_index <= len(self.log):
            lines.append("Moves: " + " ".join(self.log[self.turn_index - 1]))
        for i, text in enumerate(lines):
            surf = self.hud_font.render(text, True, (20, 20, 20))
            self.screen.blit(surf, (10, 10 + i * 22))

    def _draw_button(
        self, rect: pygame.Rect, text: str, enabled: bool
    ) -> None:
        """Draw one navigation button, greyed out when disabled."""
        color = BUTTON_COLOR if enabled else BUTTON_DISABLED_COLOR
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, (30, 30, 30), rect, 2, border_radius=6)
        label = self.hud_font.render(text, True, (255, 255, 255))
        self.screen.blit(
            label,
            (rect.centerx - label.get_width() // 2,
             rect.centery - label.get_height() // 2),
        )

    def _draw_buttons(self) -> None:
        """Position and draw the ``< Prev`` / ``Next >`` buttons."""
        w, h = self.screen.get_size()
        bw, bh = self.BUTTON_SIZE
        self._prev_rect.topleft = (w // 2 - bw - 10, h - bh - 15)
        self._next_rect.topleft = (w // 2 + 10, h - bh - 15)
        self._draw_button(self._prev_rect, "< Prev", self.turn_index > 0)
        has_next = self.turn_index < len(self.snapshots) - 1
        self._draw_button(self._next_rect, "Next >", has_next)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _go_prev(self) -> None:
        """Step the replay one turn back."""
        self.turn_index = max(0, self.turn_index - 1)

    def _go_next(self) -> None:
        """Step the replay one turn forward."""
        self.turn_index = min(len(self.snapshots) - 1, self.turn_index + 1)

    def _handle_zoom(self, event: pygame.event.Event) -> None:
        """Zoom in or out, keeping the point under the mouse fixed."""
        mx, my = pygame.mouse.get_pos()
        sw, sh = self.screen.get_width(), self.screen.get_height()
        # world point under the mouse before zoom
        wx = (mx - sw / 2) / self.zoom + self.cam_x
        wy = (my - sh / 2) / self.zoom + self.cam_y
        factor = self.ZOOM_STEP if event.y > 0 else 1 / self.ZOOM_STEP
        self.zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom * factor))
        # keep the same world point under the mouse after zoom
        self.cam_x = wx - (mx - sw / 2) / self.zoom
        self.cam_y = wy - (my - sh / 2) / self.zoom

    def _handle_event(self, event: pygame.event.Event) -> bool:
        """React to one pygame event; return ``False`` to close."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key in (pygame.K_RIGHT, pygame.K_SPACE):
                self._go_next()
            elif event.key == pygame.K_LEFT:
                self._go_prev()
            elif event.key == pygame.K_HOME:
                self.turn_index = 0
            elif event.key == pygame.K_END:
                self.turn_index = len(self.snapshots) - 1
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._next_rect.collidepoint(event.pos):
                self._go_next()
            elif self._prev_rect.collidepoint(event.pos):
                self._go_prev()
            else:
                self._dragging = True
                self._drag_mouse = event.pos
                self._drag_cam = (self.cam_x, self.cam_y)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            dx = event.pos[0] - self._drag_mouse[0]
            dy = event.pos[1] - self._drag_mouse[1]
            self.cam_x = self._drag_cam[0] - dx / self.zoom
            self.cam_y = self._drag_cam[1] - dy / self.zoom
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_zoom(event)
        return True

    def run(self) -> None:
        """Show the window and loop until the user closes it."""
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                running = running and self._handle_event(event)

            self.screen.fill((240, 240, 240))
            self._draw_connections()
            self._draw_zones()
            self._draw_drones()
            self._draw_hud()
            self._draw_buttons()
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(
        "visual.py is not an entry point: "
        "run 'python3 fly.py <map_file> --visual' (or 'make visual')"
    )
