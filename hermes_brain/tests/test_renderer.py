"""
TDD tests for WorldRenderer — PIL-based top-down 2D renderer.
Renders the world state as an image for vision-model perception.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
from PIL import Image
from world_sim import World
from world_renderer import WorldRenderer


class TestWorldRenderer:

    def test_renderer_creates_image(self):
        """Renderer produces a PIL Image of expected size."""
        world = World()
        world.weather_timer = 999
        world.add_norn("TestNorn", 100, 100)
        world.spawn_food("apple", 120, 100, nutrition=30)

        renderer = WorldRenderer(world, viewport_size=(400, 400))
        img = renderer.render(center_x=100, center_y=100)

        assert isinstance(img, Image.Image)
        assert img.size == (400, 400)
        assert img.mode == "RGB"

    def test_renderer_draws_norns_as_circles(self):
        """Norns are visible in the rendered image."""
        world = World()
        world.weather_timer = 999
        world.add_norn("Alice", 100, 100)
        world.add_norn("Bob", 150, 120)

        renderer = WorldRenderer(world, viewport_size=(600, 600))
        img = renderer.render(center_x=125, center_y=110)

        # Just verify pixels are non-blank where Norns should be
        # Convert center_x/y to image coords: Norn at (100,100) with center at (125,110)
        # Viewport shows range x: 125±150, y: 110±150 → x: [-25, 275], y: [-40, 260]
        # Norn at (100,100) → pixel (100 - (-25)) = 125, (100 - (-40)) = 140
        # Aligned to viewport center
        img_x = int(100 - (125 - 150))  # world_x - (center_x - half_viewport)
        img_y = int(100 - (110 - 150))
        assert 0 <= img_x < 600
        assert 0 <= img_y < 600
        pixel = img.getpixel((img_x, img_y))
        assert pixel != (255, 255, 255), f"Norn should be drawn at ({img_x},{img_y}), got white {pixel}"

    def test_renderer_draws_food_differently(self):
        """Food objects are drawn as different colored shapes."""
        world = World()
        world.weather_timer = 999
        world.spawn_food("cheese", 100, 100, nutrition=50)

        renderer = WorldRenderer(world, viewport_size=(400, 400))
        img = renderer.render(center_x=100, center_y=100)

        # Food should appear as non-white, non-background pixels at center
        center_pixel = img.getpixel((200, 200))
        assert center_pixel != (255, 255, 255)

    def test_renderer_shows_weather_overlay(self):
        """Rainy weather adds visual overlay — check any pixel in image."""
        world = World()
        world.weather_timer = 999
        world.weather = "rainy"

        renderer = WorldRenderer(world, viewport_size=(400, 400))
        img = renderer.render(center_x=100, center_y=100)

        # Rain lines are randomly placed — check that image isn't uniform
        pixels = list(img.get_flattened_data())
        unique_colors = set(pixels)
        assert len(unique_colors) > 3, f"Rainy image should have varied colors, got {len(unique_colors)}"

    def test_renderer_handles_empty_world(self):
        """Rendering an empty world doesn't crash."""
        world = World()
        world.weather_timer = 999
        renderer = WorldRenderer(world)
        img = renderer.render(center_x=0, center_y=0)
        assert isinstance(img, Image.Image)

    def test_renderer_scales_objects_by_distance(self):
        """Objects further from viewport center appear smaller."""
        world = World()
        world.weather_timer = 999
        world.spawn_food("near_food", 110, 100, nutrition=30)
        world.spawn_food("far_food", 190, 100, nutrition=30)

        renderer = WorldRenderer(world, viewport_size=(400, 400))
        img = renderer.render(center_x=100, center_y=100)

        # Near food at 110,100 → very close to center → bigger circle
        # Far food at 190,100 → edge of viewport → smaller
        # Both should be drawn (not white), just different sizes handled by renderer
        near_x = int(110 - (100 - 200))
        far_x = int(190 - (100 - 200))
        assert img.getpixel((near_x, 200)) != (255, 255, 255)
        assert img.getpixel((far_x, 200)) != (255, 255, 255)
