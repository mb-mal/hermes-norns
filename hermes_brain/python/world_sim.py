#!/usr/bin/env python3
"""
Hermes Norns — World Simulator
A minimal Python world for testing Norn agents without openc2e.
"""
import json
import random
import time
import math
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from collections import defaultdict

from norn_agent import NornAgent, NornDNA, rule_based_action

# ── World Objects ────────────────────────────────────────────────

@dataclass
class WorldObject:
    name: str
    obj_type: str  # food, toy, portal, plant, tool, norn
    x: float
    y: float
    edible: bool = False
    nutrition: float = 0.0
    fun: float = 0.0

@dataclass
class NornBody:
    """Physical body of a Norn in the world."""
    name: str
    x: float
    y: float
    agent: NornAgent
    alive: bool = True
    age: int = 0
    life_stage: str = "baby"
    hunger: float = 0.5
    fatigue: float = 0.3
    boredom: float = 0.5
    loneliness: float = 0.4
    fear: float = 0.1
    pain: float = 0.0
    thirst: float = 0.3
    anger: float = 0.1
    sex_drive: float = 0.0
    crowded: float = 0.1

    # Memory
    memory_log: list = field(default_factory=list)

    def distance_to(self, obj: WorldObject) -> float:
        return math.sqrt((self.x - obj.x)**2 + (self.y - obj.y)**2)

    def visible_objects(self, world_objects: list, max_dist: float = 300) -> list:
        visible = []
        for obj in world_objects:
            if obj.name == self.name:
                continue
            d = self.distance_to(obj)
            if d <= max_dist:
                direction = "front"
                if obj.x < self.x - 30:
                    direction = "left"
                elif obj.x > self.x + 30:
                    direction = "right"
                visible.append({
                    "type": obj.obj_type,
                    "name": obj.name,
                    "distance": round(d),
                    "direction": direction,
                })
        return visible


# ── World ─────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.objects: list[WorldObject] = []
        self.norns: list[NornBody] = []
        self.tick_count = 0
        self.event_log: list[str] = []

    def add_object(self, obj: WorldObject):
        self.objects.append(obj)

    def add_norn(self, name: str, x: float, y: float, dna: Optional[NornDNA] = None) -> NornBody:
        agent = NornAgent(use_llm=False)
        if dna:
            agent.state.dna = dna
        else:
            agent.state.dna = NornDNA(name=name)
        body = NornBody(name=name, x=x, y=y, agent=agent)
        self.norns.append(body)
        self.objects.append(WorldObject(name=name, obj_type="norn", x=x, y=y))
        return body

    def spawn_food(self, name: str, x: float, y: float, nutrition: float = 30):
        self.add_object(WorldObject(
            name=name, obj_type="food", x=x, y=y,
            edible=True, nutrition=nutrition
        ))

    def spawn_toy(self, name: str, x: float, y: float, fun: float = 20):
        self.add_object(WorldObject(
            name=name, obj_type="toy", x=x, y=y, fun=fun
        ))

    def _update_drives(self, norn: NornBody):
        """Drives increase over time (needs grow)."""
        norn.age += 1
        norn.hunger = min(1.0, norn.hunger + 0.008)
        norn.fatigue = min(1.0, norn.fatigue + 0.005)
        norn.boredom = min(1.0, norn.boredom + 0.006)
        norn.loneliness = min(1.0, norn.loneliness + 0.005)
        norn.thirst = min(1.0, norn.thirst + 0.006)
        norn.sex_drive = min(1.0, norn.sex_drive + 0.002)

        # Life stage
        if norn.age < 100:
            norn.life_stage = "baby"
        elif norn.age < 500:
            norn.life_stage = "child"
        elif norn.age < 2000:
            norn.life_stage = "adolescent"
        elif norn.age < 5000:
            norn.life_stage = "adult"
        else:
            norn.life_stage = "elder"

    def _execute_action(self, norn: NornBody, action: dict):
        """Apply action effects to the world."""
        act = action.get("action", "QUIET")
        target_name = action.get("target", "")
        thought = action.get("thought", "")

        target_obj = None
        for obj in self.objects:
            if obj.name == target_name:
                target_obj = obj
                break

        if act == "EAT" and target_obj and target_obj.edible:
            if norn.distance_to(target_obj) < 20:
                norn.hunger = max(0, norn.hunger - target_obj.nutrition / 100)
                self.objects.remove(target_obj)
                self.event_log.append(f"🍽️  {norn.name} ate {target_name}")
                norn.memory_log.append(f"ate {target_name} — tasty!")
            else:
                norn.x += (target_obj.x - norn.x) * 0.3
                norn.y += (target_obj.y - norn.y) * 0.3

        elif act == "PLAY" and target_obj and target_obj.fun > 0:
            if norn.distance_to(target_obj) < 20:
                norn.boredom = max(0, norn.boredom - target_obj.fun / 100)
                self.event_log.append(f"🎮 {norn.name} played with {target_name}")
                norn.memory_log.append(f"played with {target_name} — fun!")
            else:
                norn.x += (target_obj.x - norn.x) * 0.3
                norn.y += (target_obj.y - norn.y) * 0.3

        elif act == "APPROACH" and target_obj:
            norn.x += (target_obj.x - norn.x) * 0.2
            norn.y += (target_obj.y - norn.y) * 0.2
            if norn.distance_to(target_obj) < 30:
                self.event_log.append(f"👋 {norn.name} approached {target_name}")
                norn.loneliness = max(0, norn.loneliness - 0.3)
                norn.memory_log.append(f"met {target_name}")

        elif act == "REST":
            norn.fatigue = max(0, norn.fatigue - 0.15)
            self.event_log.append(f"😴 {norn.name} is resting")

        elif act == "TRAVEL":
            direction = target_name
            step = 30
            if direction == "left":
                norn.x -= step
            elif direction == "right":
                norn.x += step
            elif direction == "up":
                norn.y -= step
            elif direction == "down":
                norn.y += step
            elif direction == "away":
                norn.x += random.choice([-step, step])
                norn.y += random.choice([-step, step])
            else:
                norn.x += random.uniform(-step, step)
                norn.y += random.uniform(-step, step)
            norn.fear = max(0, norn.fear - 0.1)
            self.event_log.append(f"🚶 {norn.name} moves {direction}")

        elif act == "SPEAK":
            word = target_name
            self.event_log.append(f"💬 {norn.name} says '{word}'")

        elif act == "BREED" and target_obj and target_obj.obj_type == "norn":
            target_norn = None
            for nb in self.norns:
                if nb.name == target_name:
                    target_norn = nb
                    break
            if target_norn and norn.distance_to(target_obj) < 30:
                norn.sex_drive = 0
                target_norn.sex_drive = 0
                baby_name = f"{norn.name[:3]}{target_norn.name[:3]}_{random.randint(100,999)}"
                baby_x = (norn.x + target_norn.x) / 2
                baby_y = (norn.y + target_norn.y) / 2
                baby_dna = NornDNA(name=baby_name)
                if norn.agent.state.dna and target_norn.agent.state.dna:
                    for trait in ["curiosity", "aggression", "sociability", "playfulness", "cautiousness", "intelligence"]:
                        setattr(baby_dna, trait, (getattr(norn.agent.state.dna, trait) + getattr(target_norn.agent.state.dna, trait)) / 2)
                self.add_norn(baby_name, baby_x, baby_y, baby_dna)
                self.event_log.append(f"🐣 {baby_name} was born! ({norn.name} + {target_norn.name})")

        elif act == "QUIET":
            pass  # idle — don't log to avoid spam

        # Update norn position in world objects
        for obj in self.objects:
            if obj.name == norn.name:
                obj.x = norn.x
                obj.y = norn.y

    def tick(self):
        """One simulation step."""
        self.tick_count += 1
        self.event_log = []

        for norn in self.norns:
            if not norn.alive:
                continue

            self._update_drives(norn)

            # Build perception
            perception = {
                "tick": self.tick_count,
                "drives": {
                    "hunger": norn.hunger, "thirst": norn.thirst,
                    "fatigue": norn.fatigue, "boredom": norn.boredom,
                    "loneliness": norn.loneliness, "fear": norn.fear,
                    "pain": norn.pain, "anger": norn.anger,
                    "sex_drive": norn.sex_drive, "crowded": norn.crowded,
                },
                "visible_objects": norn.visible_objects(self.objects),
                "learned_words": norn.agent.state.learned_words,
                "recent_memories": norn.agent.state.memories[-10:],
                "dna_traits": norn.agent.state.dna.__dict__ if norn.agent.state.dna else {},
                "life_stage": norn.life_stage,
            }

            action = norn.agent.perceive(perception)
            self._execute_action(norn, action)

    def status(self) -> str:
        lines = [f"═══ Tick {self.tick_count} ═══"]
        for norn in self.norns:
            lines.append(
                f"  {norn.name} [{norn.life_stage}] "
                f"🍽️{int(norn.hunger*100):>3} 😴{int(norn.fatigue*100):>3} "
                f"🎮{int(norn.boredom*100):>3} 👤{int(norn.loneliness*100):>3} "
                f"📍({int(norn.x)},{int(norn.y)})"
            )
        for evt in self.event_log:
            lines.append(f"  {evt}")
        objects = [o for o in self.objects if o.obj_type != "norn"]
        if objects:
            food = [o for o in objects if o.obj_type == "food"]
            toys = [o for o in objects if o.obj_type == "toy"]
            parts = []
            if food: parts.append(f"{len(food)}🍽️")
            if toys: parts.append(f"{len(toys)}🎮")
            lines.append(f"  World: {', '.join(parts)}")
        return "\n".join(lines)


# ── Demo ──────────────────────────────────────────────────────────

def demo():
    print("🌍 Hermes Norns — World Simulator Demo\n")
    world = World()

    # Create starting population
    world.add_norn("Alice", 100, 100, NornDNA(
        name="Alice", curiosity=0.9, sociability=0.8, playfulness=0.7, cautiousness=0.2
    ))
    world.add_norn("Bob", 300, 100, NornDNA(
        name="Bob", curiosity=0.3, sociability=0.4, playfulness=0.2, cautiousness=0.8, aggression=0.6
    ))

    # Spawn food and toys
    world.spawn_food("carrot", 80, 120, nutrition=30)
    world.spawn_food("cheese", 250, 80, nutrition=50)
    world.spawn_toy("ball", 180, 200, fun=25)
    world.spawn_toy("bell", 350, 150, fun=15)

    # Run simulation
    for _ in range(100):
        world.tick()

        # Respawn food occasionally
        if random.random() < 0.08:
            food_names = ["carrot", "apple", "cheese", "lemon", "honey"]
            world.spawn_food(
                random.choice(food_names),
                random.uniform(0, 400),
                random.uniform(0, 300),
                random.randint(20, 50)
            )

        status = world.status()
        if world.event_log:  # only print when something happened
            print(status)
            print()
            time.sleep(0.3)

    print(f"\n🏁 Simulation complete. {len(world.norns)} Norns alive.")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    demo()
