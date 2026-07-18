"""
Hermes Norns — Game Runner
===========================
Playable game loop with save/load, console UI, and configurable speed.
"""
import json
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from world_sim import World, WorldObject, NornBody
from norn_agent import NornAgent, NornDNA
from action_packet import parse_llm_response
from world_renderer import WorldRenderer

SAVE_DIR = Path.home() / ".hermes-norns" / "saves"


class HermesNornsGame:
    """Complete game — world simulation + agent control + save/load."""

    def __init__(self):
        self.world = World()
        self.tick_delay = 0.05  # 50ms/tick ≈ 20 TPS
        self.auto_save_interval = 300  # ticks
        self.use_llm = False  # set True for LLM-powered Norns
        self.llm_model = "deepseek-v4-pro"
        SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # ── World Setup ──────────────────────────────────────────────

    def new_game(self, norn_count=3):
        """Start a fresh game with initial Norns."""
        self.world = World()
        for i in range(norn_count):
            x = 100 + i * 80
            y = 150
            dna = NornDNA(name=f"Norn_{i+1}")
            if i == 0:
                dna.curiosity = 0.9
                dna.sociability = 0.7
            elif i == 1:
                dna.curiosity = 0.3
                dna.cautiousness = 0.9
            else:
                dna.playfulness = 0.9
                dna.sociability = 0.9
            norn = self.world.add_norn(dna.name, x, y, dna)
            norn.life_stage = ["baby", "child", "adult"][i % 3]

        # Scatter food
        for _ in range(20):
            self.world.spawn_food(
                ["cheese", "carrot", "apple", "berry", "honey"][_ % 5],
                (100 + (_ % 5) * 80 + (_ // 5) * 20),
                (100 + (_ // 5) * 60),
                nutrition=20 + _ * 2,
            )

        # Toys
        for i, toy_name in enumerate(["ball", "rattle", "puzzle"]):
            self.world.spawn_food(toy_name, 120 + i * 100, 250, nutrition=0)
            # Mark as toy
            for obj in self.world.objects:
                if obj.name == toy_name:
                    obj.obj_type = "toy"

        self.world.event_log = ["🎮 New game started!"]
        return self

    # ── Save/Load ────────────────────────────────────────────────

    def save(self, name: str = "autosave"):
        """Save game state to disk."""
        path = SAVE_DIR / f"{name}.norns"
        state = {
            "version": "1.0",
            "world": self.world.to_dict(),
            "tick_delay": self.tick_delay,
            "use_llm": self.use_llm,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)
        return str(path)

    def load(self, name: str = "autosave") -> bool:
        """Load game state from disk."""
        path = SAVE_DIR / f"{name}.norns"
        if not path.exists():
            return False

        with open(path, "rb") as f:
            state = pickle.load(f)

        if state.get("version") != "1.0":
            return False

        self.world = World.from_dict(state["world"])
        self.tick_delay = state.get("tick_delay", 0.05)
        self.use_llm = state.get("use_llm", False)
        self.world.event_log.append(f"💾 Loaded: {name}")
        return True

    def list_saves(self) -> list:
        """List available save files."""
        saves = []
        for f in sorted(SAVE_DIR.glob("*.norns")):
            saves.append(f.stem)
        return saves

    # ── Game Loop ────────────────────────────────────────────────

    def tick(self) -> list:
        """Advance one game tick. Returns list of event strings."""
        self.world.tick()
        events = self.world.event_log[-5:]  # last 5 events
        self.world.event_log = self.world.event_log[-200:]  # keep last 200

        # Auto-save
        if self.world.tick_count % self.auto_save_interval == 1 and self.world.tick_count > 1:
            self.save("autosave")

        return events

    def status(self) -> dict:
        """Return game status for UI rendering."""
        alive = [n for n in self.world.norns if n.alive]
        dead = [n for n in self.world.norns if not n.alive]
        foods = sum(1 for o in self.world.objects if o.obj_type == "food")
        toys = sum(1 for o in self.world.objects if o.obj_type == "toy")
        plants = sum(1 for o in self.world.objects if o.obj_type == "plant")
        predators = sum(1 for o in self.world.objects if o.obj_type == "predator")

        return {
            "tick": self.world.tick_count,
            "weather": self.world.weather,
            "population": len(alive),
            "dead": len(dead),
            "food_count": foods,
            "toys": toys,
            "plants": plants,
            "predators": predators,
            "norns": [
                {
                    "name": n.name,
                    "life_stage": n.life_stage,
                    "mood": n.mood,
                    "hunger": f"{n.hunger:.0%}",
                    "fatigue": f"{n.fatigue:.0%}",
                    "fitness": f"{n.fitness:.1f}",
                    "species": n.species_id,
                    "alive": n.alive,
                }
                for n in self.world.norns
            ],
        }

    # ── Console UI ───────────────────────────────────────────────

    def render_console(self):
        """Render game state to console (text-based UI)."""
        s = self.status()
        os.system("clear" if os.name != "nt" else "cls")

        weather_icons = {"sunny": "☀️", "cloudy": "☁️", "rainy": "🌧️"}
        print(f"{'='*60}")
        print(f"  🧬 HERMES NORNS")
        print(f"  {weather_icons.get(s['weather'], '❓')} Tick {s['tick']} | {s['weather'].upper()}")
        print(f"  👥 {s['population']} alive | 💀 {s['dead']} dead")
        print(f"  🍎 {s['food_count']} food | 🎯 {s['toys']} toys | 🌱 {s['plants']} plants | 🦖 {s['predators']} predators")
        print(f"{'='*60}")

        for norn_data in s["norns"]:
            alive_mark = "💚" if norn_data["alive"] else "💀"
            print(f"  {alive_mark} {norn_data['name']:12s} [{norn_data['life_stage']:10s}] "
                  f"🍽️{norn_data['hunger']:>5s} 😴{norn_data['fatigue']:>5s} "
                  f"📊{norn_data['fitness']:>6s} | {norn_data['mood']}")
        print(f"{'─'*60}")

    def run_console(self, max_ticks=None, render_every=1):
        """Run game loop with console rendering."""
        try:
            tick_count = 0
            while max_ticks is None or tick_count < max_ticks:
                events = self.tick()
                tick_count += 1

                if tick_count % render_every == 0:
                    self.render_console()

                    # Show recent events
                    for event in events:
                        print(f"  {event}")

                time.sleep(self.tick_delay)

                # Stop if all Norns are dead
                if all(not n.alive for n in self.world.norns):
                    print("\n💀 All Norns have died. Game over.")
                    break

        except KeyboardInterrupt:
            print(f"\n⏸️  Paused at tick {tick_count}. Saving...")
            self.save()
            print("💾 Saved. Goodbye!")


# ── CLI entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hermes Norns — AI Life Simulation")
    parser.add_argument("--new", action="store_true", help="Start new game")
    parser.add_argument("--load", type=str, default=None, help="Load save by name")
    parser.add_argument("--list-saves", action="store_true", help="List save files")
    parser.add_argument("--ticks", type=int, default=None, help="Run N ticks and exit")
    parser.add_argument("--delay", type=float, default=0.05, help="Tick delay in seconds")
    parser.add_argument("--llm", action="store_true", help="Use LLM for Norn brains")
    parser.add_argument("--render", action="store_true", help="Render world to PNG")
    args = parser.parse_args()

    game = HermesNornsGame()

    if args.list_saves:
        saves = game.list_saves()
        print("Saves:", saves if saves else "none")
        sys.exit(0)

    if args.load:
        if game.load(args.load):
            print(f"Loaded: {args.load}")
        else:
            print(f"Save '{args.load}' not found. Starting new game.")
            game.new_game()
    elif args.new:
        game.new_game()
    else:
        # Default: new game
        game.new_game()

    game.tick_delay = args.delay
    game.use_llm = args.llm

    if args.render:
        from world_renderer import WorldRenderer
        r = WorldRenderer(game.world)
        img = r.render(center_x=200, center_y=150)
        path = str(Path.home() / "norns_screenshot.png")
        img.save(path)
        print(f"Rendered: {path}")

    if args.ticks:
        game.run_console(max_ticks=args.ticks, render_every=50)
    else:
        game.run_console(render_every=1)
