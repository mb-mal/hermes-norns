"""
Tests for Hermes Norns — Weather System.
TDD: RED phase — all tests must FAIL first.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
from world_sim import World, WorldObject


class TestWeatherSystem:
    """Weather affects the world and Norn behavior."""

    def test_world_starts_with_weather(self):
        """World initializes with a weather state."""
        world = World()
        assert hasattr(world, 'weather')
        assert world.weather in ("sunny", "cloudy", "rainy")
        assert hasattr(world, 'weather_timer')

    def test_weather_changes_over_time(self):
        """Weather changes after enough ticks pass."""
        world = World()
        initial = world.weather
        
        # Weather should stay same for a while
        for _ in range(50):
            world.tick()
        assert world.weather == initial  # not changed yet
        
        # After many ticks, should eventually change
        changed = False
        for _ in range(500):
            world.tick()
            if world.weather != initial:
                changed = True
                break
        assert changed, f"Weather never changed from {initial}"

    def test_rain_accelerates_plant_growth(self):
        """Plants grow faster during rain."""
        world = World()
        world.weather = "rainy"
        world.weather_timer = 999  # prevent weather change
        
        plant = WorldObject(name="test_plant", obj_type="plant", x=100, y=100)
        plant.growth = 0
        plant.growth_rate = 0.05  # slower so it doesn't reset within 10 ticks
        world.add_object(plant)
        
        # Tick during rain — rain gives 2x growth
        for _ in range(10):
            world.tick()
        
        assert plant.growth > 0.5, f"Plant should grow fast in rain, got growth={plant.growth}"
        assert plant.growth < 1.0, f"Growth shouldn't reset yet, got {plant.growth}"

    def test_weather_reported_in_status(self):
        """World status includes current weather."""
        world = World()
        world.weather = "rainy"
        status = world.status()
        assert "🌧️ rainy" in status or "rainy" in status.lower()


class TestPlantObjects:
    """Plants are living world objects that grow and can be harvested."""

    def test_plant_has_growth(self):
        """Plants have a growth attribute."""
        plant = WorldObject(name="carrot_plant", obj_type="plant", x=0, y=0)
        assert hasattr(plant, 'growth')
        assert hasattr(plant, 'growth_rate')
        assert 0 <= plant.growth <= 1

    def test_plant_grows_over_time(self):
        """Plant growth increases each tick."""
        world = World()
        world.weather_timer = 999  # prevent weather change
        plant = WorldObject(name="test_plant", obj_type="plant", x=0, y=0)
        plant.growth = 0
        plant.growth_rate = 0.03  # slow enough not to reset
        world.add_object(plant)
        
        for _ in range(20):
            world.tick()
        
        assert plant.growth > 0.3, f"Plant barely grew: {plant.growth}"
        assert plant.growth < 1.0, f"Growth reset: {plant.growth}"

    def test_fully_grown_plant_produces_food(self):
        """When a plant reaches full growth, it spawns harvestable food."""
        world = World()
        plant = WorldObject(name="berry_bush", obj_type="plant", x=100, y=100)
        plant.growth = 0.99
        plant.growth_rate = 0.1
        world.add_object(plant)
        
        # Tick until fully grown
        world.tick()
        
        # Should have spawned food
        foods = [o for o in world.objects if o.obj_type == "food"]
        assert len(foods) > 0, f"No food spawned from fully grown plant"


class TestNornAgingAndDeath:
    """Norns age and eventually die."""

    def test_norn_has_lifespan(self):
        """Norns have a maximum age."""
        from world_sim import NornBody
        from norn_agent import NornAgent
        
        agent = NornAgent()
        body = NornBody(name="Test", x=0, y=0, agent=agent)
        assert hasattr(body, 'max_age')
        assert body.max_age > 0

    def test_norn_dies_of_old_age(self):
        """Norn dies when age exceeds max_age."""
        world = World()
        norn = world.add_norn("OldNorn", 100, 100)
        norn.age = 9990
        norn.max_age = 10000
        
        # Tick past max_age
        for _ in range(20):
            world.tick()
        
        assert not norn.alive, f"Norn should be dead after exceeding max_age"


class TestObjectDiversity:
    """World supports diverse object types."""

    def test_predator_object_type(self):
        """Predators are dangerous world objects."""
        predator = WorldObject(name="grendel", obj_type="predator", x=50, y=50, danger_level=0.8)
        assert hasattr(predator, 'danger_level')
        assert predator.danger_level > 0

    def test_tool_object_type(self):
        """Tools can be used to build or modify the world."""
        tool = WorldObject(name="shovel", obj_type="tool", x=50, y=50, tool_type="dig")
        assert hasattr(tool, 'tool_type')
        assert tool.tool_type in ("build", "dig", "carry", "protect")

    def test_portal_teleports_norns(self):
        """Portals move Norns to a linked location."""
        world = World()
        world.weather_timer = 999
        portal = WorldObject(name="warp_gate", obj_type="portal", x=10, y=10)
        portal.link_x = 500
        portal.link_y = 500
        world.add_object(portal)
        
        norn = world.add_norn("Traveler", 12, 12)
        
        # The norn is near the portal — tick should trigger teleport
        world.tick()
        
        # Should have teleported to (500, 500) or near it (action may move slightly)
        assert abs(norn.x - 500) < 50, f"Norn should be near (500,500), got ({norn.x},{norn.y})"
        assert abs(norn.y - 500) < 50, f"Norn should be near (500,500), got ({norn.x},{norn.y})"
