"""
WorldRenderer — PIL-based top-down 2D renderer for Norn vision.
Renders the world state as an image that can be fed to vision models (GPT-4V, LLaVA).
"""
import math
import random
from PIL import Image, ImageDraw, ImageFont
from world_sim import World, NornBody, WorldObject


# ── Color palette ──────────────────────────────────────────────────

GROUND_COLOR = (34, 139, 34)       # Forest green
GROUND_SUNNY = (60, 160, 60)      # Brighter for sunny
GROUND_RAINY = (30, 100, 30)       # Darker for rainy
GROUND_CLOUDY = (45, 140, 45)      # In-between

NORN_COLORS = {
    "baby": (255, 182, 193),      # Light pink
    "child": (135, 206, 250),     # Light blue
    "adolescent": (152, 251, 152), # Pale green
    "adult": (255, 215, 0),        # Gold
    "elder": (192, 192, 192),      # Silver
}

OBJECT_COLORS = {
    "food": (255, 69, 0),          # Orange-red
    "toy": (255, 215, 0),          # Gold
    "plant": (50, 205, 50),        # Lime green
    "predator": (220, 20, 60),     # Crimson
    "portal": (138, 43, 226),      # Blue-violet
    "tool": (139, 90, 43),         # Brown
}

OBJECT_SHAPES = {
    "food": "star",
    "toy": "diamond",
    "plant": "leaf",
    "predator": "triangle",
    "portal": "circle",
    "tool": "square",
}

MOOD_HALO_COLORS = {
    "happy": (255, 255, 100),
    "sad": (100, 100, 200),
    "excited": (255, 200, 50),
    "scared": (200, 200, 200),
    "angry": (255, 50, 50),
    "curious": (50, 200, 50),
    "playful": (200, 100, 255),
    "tired": (150, 150, 150),
    "loving": (255, 150, 200),
    "lonely": (100, 100, 150),
}


class WorldRenderer:
    """Renders world state as a 2D top-down image."""

    def __init__(self, world: World, viewport_size=(512, 512)):
        self.world = world
        self.viewport_w, self.viewport_h = viewport_size
        # Try to load a font, fall back to default
        try:
            self.font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
            self.font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 8)
        except (IOError, OSError):
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def render(self, center_x=0, center_y=0) -> Image.Image:
        """Render the world centered at (center_x, center_y).

        Viewport shows a fixed-size window around the center.
        Objects are drawn at their world positions relative to center.
        """
        img = Image.new("RGB", (self.viewport_w, self.viewport_h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        half_w = self.viewport_w // 2
        half_h = self.viewport_h // 2

        # ── Background ──
        weather = self.world.weather
        if weather == "sunny":
            bg = GROUND_SUNNY
        elif weather == "rainy":
            bg = GROUND_RAINY
        else:
            bg = GROUND_CLOUDY

        draw.rectangle([0, 0, self.viewport_w, self.viewport_h], fill=bg)

        # ── Grid lines ──
        for x in range(0, self.viewport_w, 50):
            draw.line([(x, 0), (x, self.viewport_h)], fill=(255, 255, 255, 30), width=1)
        for y in range(0, self.viewport_h, 50):
            draw.line([(0, y), (self.viewport_w, y)], fill=(255, 255, 255, 30), width=1)

        # ── Plants ──
        for obj in self.world.objects:
            if obj.obj_type == "plant":
                ix, iy = self._world_to_image(obj.x, obj.y, center_x, center_y)
                if 0 <= ix < self.viewport_w and 0 <= iy < self.viewport_h:
                    growth = getattr(obj, "growth", 0.5)
                    r = int(5 + growth * 10)
                    draw.ellipse([ix - r, iy - r, ix + r, iy + r],
                                fill=(40, 180, 40), outline=(20, 120, 20))

        # ── Objects (food, toys, portals, predators) ──
        for obj in self.world.objects:
            if obj.obj_type in ("plant", "norn"):
                continue
            ix, iy = self._world_to_image(obj.x, obj.y, center_x, center_y)
            if not (0 <= ix < self.viewport_w and 0 <= iy < self.viewport_h):
                continue

            color = OBJECT_COLORS.get(obj.obj_type, (200, 200, 200))
            shape = OBJECT_SHAPES.get(obj.obj_type, "square")
            r = 6

            if shape == "star":
                self._draw_star(draw, ix, iy, r, color)
            elif shape == "diamond":
                self._draw_diamond(draw, ix, iy, r, color)
            elif shape == "triangle":
                self._draw_triangle(draw, ix, iy, r, color)
            elif shape == "leaf":
                draw.ellipse([ix - r, iy - r // 2, ix + r, iy + r // 2], fill=color)
            else:
                draw.rectangle([ix - r, iy - r, ix + r, iy + r], fill=color)

            # Label
            name = obj.name[:8]
            if name:
                draw.text((ix + 8, iy - 4), name, fill=(255, 255, 255), font=self.font_small)

        # ── Norns ──
        for norn in self.world.norns:
            if not norn.alive:
                continue
            ix, iy = self._world_to_image(norn.x, norn.y, center_x, center_y)
            if not (0 <= ix < self.viewport_w and 0 <= iy < self.viewport_h):
                continue

            # Mood halo
            halo_color = MOOD_HALO_COLORS.get(norn.mood, (200, 200, 200))
            halo_r = 14
            draw.ellipse([ix - halo_r, iy - halo_r, ix + halo_r, iy + halo_r],
                         fill=halo_color, outline=(255, 255, 255, 100))

            # Body — color by life stage
            body_color = NORN_COLORS.get(norn.life_stage, (200, 200, 200))
            body_r = 10
            draw.ellipse([ix - body_r, iy - body_r, ix + body_r, iy + body_r],
                         fill=body_color, outline=(0, 0, 0))

            # Direction indicator (tiny line)
            draw.line([(ix, iy), (ix + 8, iy)], fill=(0, 0, 0), width=2)

            # Name label
            draw.text((ix + 12, iy - 4), norn.name[:10], fill=(255, 255, 255), font=self.font_small)

            # Hunger bar (small red bar above)
            hunger = norn.hunger
            bar_w = 16
            bar_h = 3
            bar_x = ix - bar_w // 2
            bar_y = iy - 16
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(60, 60, 60))
            fill_w = int(bar_w * hunger)
            if fill_w > 0:
                draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
                              fill=(255, 50, 50))

        # ── Weather overlay ──
        if weather == "rainy":
            for _ in range(50):
                rx = random.randint(0, self.viewport_w)
                ry = random.randint(0, self.viewport_h)
                draw.line([(rx, ry), (rx + 1, ry + 4)], fill=(100, 150, 200), width=1)

        elif weather == "cloudy":
            for _ in range(8):
                cx = random.randint(0, self.viewport_w)
                cy = random.randint(0, self.viewport_h // 3)
                draw.ellipse([cx - 15, cy - 8, cx + 15, cy + 8], fill=(180, 180, 190, 60))

        # ── Info overlay ──
        info = f"Tick {self.world.tick_count} | {weather.upper()}"
        draw.text((5, 5), info, fill=(255, 255, 255), font=self.font)
        # Draw a dark backdrop for the text
        draw.rectangle([3, 3, 3 + len(info) * 6 + 4, 3 + 14], fill=(0, 0, 0, 120))

        return img

    def _world_to_image(self, x, y, cx, cy):
        """Convert world coordinates to image pixel coordinates."""
        half_w = self.viewport_w // 2
        half_h = self.viewport_h // 2
        return (int(x - cx + half_w), int(y - cy + half_h))

    # ── Shape helpers ──

    def _draw_star(self, draw, x, y, r, color):
        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            dist = r if i % 2 == 0 else r // 2
            px = x + int(dist * math.cos(angle))
            py = y - int(dist * math.sin(angle))
            points.append((px, py))
        draw.polygon(points, fill=color, outline=(0, 0, 0))

    def _draw_diamond(self, draw, x, y, r, color):
        points = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
        draw.polygon(points, fill=color, outline=(0, 0, 0))

    def _draw_triangle(self, draw, x, y, r, color):
        points = [(x, y - r), (x + r, y + r), (x - r, y + r)]
        draw.polygon(points, fill=color, outline=(0, 0, 0))
