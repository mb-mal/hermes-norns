#!/usr/bin/env python3
"""
Hermes Norns — Full Demo
Multi-agent simulation with logging, analytics, and DNA-driven personalities.
"""
import json
import random
import time
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from norn_agent import NornDNA
from llm_agent import LLMNornAgent
from world_sim import World, NornBody


# ── Predefined Norn personalities ────────────────────────────────

PERSONALITIES = {
    "CuriousExplorer": NornDNA(
        name="CuriousExplorer", curiosity=0.95, sociability=0.5,
        playfulness=0.7, cautiousness=0.1, aggression=0.1, intelligence=0.8
    ),
    "SocialButterfly": NornDNA(
        name="SocialButterfly", curiosity=0.5, sociability=0.95,
        playfulness=0.8, cautiousness=0.3, aggression=0.05, intelligence=0.6
    ),
    "CautiousHermit": NornDNA(
        name="CautiousHermit", curiosity=0.1, sociability=0.1,
        playfulness=0.2, cautiousness=0.95, aggression=0.2, intelligence=0.5
    ),
    "AggressiveBully": NornDNA(
        name="AggressiveBully", curiosity=0.4, sociability=0.3,
        playfulness=0.3, cautiousness=0.2, aggression=0.9, intelligence=0.4
    ),
    "PlayfulGenius": NornDNA(
        name="PlayfulGenius", curiosity=0.85, sociability=0.7,
        playfulness=0.95, cautiousness=0.4, aggression=0.1, intelligence=0.9
    ),
}


def run_demo(ticks: int = 500, use_llm: bool = False, verbose: bool = True):
    """Run a full multi-agent simulation."""
    print("🌍 Hermes Norns — Live Simulation")
    print(f"   Mode: {'LLM' if use_llm else 'Rule-based'} | Ticks: {ticks}")
    print(f"   Time: {time.strftime('%H:%M:%S')}")
    print()

    world = World()
    stats = defaultdict(list)

    # Create diverse starting population
    p1 = PERSONALITIES["CuriousExplorer"]
    p1.name = "Alice"
    dna1 = NornDNA(**{k: v for k, v in p1.__dict__.items() if k != 'name'})
    dna1.name = "Alice"
    world.add_norn("Alice", 100, 100, dna1)

    p2 = PERSONALITIES["SocialButterfly"]
    p2.name = "Bob"
    dna2 = NornDNA(**{k: v for k, v in p2.__dict__.items() if k != 'name'})
    dna2.name = "Bob"
    world.add_norn("Bob", 300, 100, dna2)

    p3 = PERSONALITIES["CautiousHermit"]
    p3.name = "Charlie"
    dna3 = NornDNA(**{k: v for k, v in p3.__dict__.items() if k != 'name'})
    dna3.name = "Charlie"
    world.add_norn("Charlie", 200, 250, dna3)

    # Override agents with LLM if requested
    if use_llm:
        for norn in world.norns:
            norn.agent = LLMNornAgent(use_llm=True)
            norn.agent.state.dna = norn.agent.state.dna  # preserve

    # Spawn initial objects
    world.spawn_food("carrot", 80, 120, nutrition=30)
    world.spawn_food("cheese", 250, 80, nutrition=50)
    world.spawn_food("apple", 350, 200, nutrition=40)
    world.spawn_food("lemon", 150, 300, nutrition=20)
    world.spawn_toy("ball", 180, 180, fun=25)
    world.spawn_toy("bell", 350, 150, fun=15)
    world.spawn_toy("puzzle", 100, 300, fun=35)

    # Run simulation
    for _ in range(ticks):
        world.tick()

        # Respawn food occasionally
        if random.random() < 0.10:
            foods = ["carrot", "apple", "cheese", "lemon", "honey", "berry", "nut"]
            world.spawn_food(
                random.choice(foods),
                random.uniform(0, 400),
                random.uniform(0, 350),
                random.randint(15, 50)
            )

        # Track stats
        for norn in world.norns:
            if norn.alive:
                stats[f"{norn.name}_hunger"].append(norn.hunger)
                stats[f"{norn.name}_fatigue"].append(norn.fatigue)
                stats[f"{norn.name}_boredom"].append(norn.boredom)
                stats[f"{norn.name}_loneliness"].append(norn.loneliness)

        # Print events
        if verbose and world.event_log:
            status = world.status()
            interesting = [e for e in world.event_log if "idle" not in e]
            if interesting or world.tick_count % 50 == 0:
                print(status)
                print()

    # ── Final Report ──────────────────────────────────────────
    print("\n" + "=" * 50)
    print("📊 SIMULATION REPORT")
    print("=" * 50)

    print(f"\nTotal ticks: {ticks}")
    print(f"Population: {len(world.norns)} Norns")
    
    for norn in world.norns:
        if not norn.alive:
            continue
        dna = norn.agent.state.dna
        mems = norn.agent.state.memories

        # Count action types
        actions = defaultdict(int)
        for m in mems:
            for act in ["EAT", "PLAY", "REST", "APPROACH", "TRAVEL", "BREED", "SPEAK", "QUIET"]:
                if act in m:
                    actions[act] += 1
                    break

        avg_hunger = sum(stats[f"{norn.name}_hunger"][-100:]) / min(100, len(stats[f"{norn.name}_hunger"]))
        avg_fatigue = sum(stats[f"{norn.name}_fatigue"][-100:]) / min(100, len(stats[f"{norn.name}_fatigue"]))

        print(f"\n🧬 {norn.name} [{norn.life_stage}]")
        print(f"   DNA: curiosity={dna.curiosity:.2f} social={dna.sociability:.2f} "
              f"playful={dna.playfulness:.2f} cautious={dna.cautiousness:.2f}")
        print(f"   Avg drives: 🍽️{avg_hunger:.0%} 😴{avg_fatigue:.0%}")
        print(f"   Actions: {dict(actions)}")
        print(f"   Memories: {len(mems)} events")
        if mems:
            print(f"   Latest: {mems[-1]}")

    # World state
    foods = [o for o in world.objects if o.obj_type == "food"]
    toys = [o for o in world.objects if o.obj_type == "toy"]
    print(f"\n🌍 World: {len(foods)} foods, {len(toys)} toys")

    print("\n✅ Demo complete.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Norns Multi-Agent Simulation")
    parser.add_argument("--ticks", type=int, default=300, help="Number of ticks to simulate")
    parser.add_argument("--llm", action="store_true", help="Use LLM backend (falls back to rules if unavailable)")
    parser.add_argument("--quiet", action="store_true", help="Only show final report")
    args = parser.parse_args()

    run_demo(ticks=args.ticks, use_llm=args.llm, verbose=not args.quiet)
