"""
Multi-agent LLM driver — each Norn gets its own LLM call (batched or parallel).
Solves the latency problem: N Norns × 30s = N × 30s sequentially.
Strategies:
  1. BATCH: one prompt → all Norn decisions at once
  2. PARALLEL: N concurrent subprocess calls
  3. CACHED: skip LLM when nothing changed
"""
import asyncio
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from perception_v2 import format_perception_v2
from action_packet import parse_llm_response


BATCH_PROMPT_TEMPLATE = """You are the collective brain of {n} Norns. For each Norn, decide one action.

{perceptions}

For each Norn, return exactly one JSON action. Output ALL actions in a JSON array:
[
  {{"norn": "NornName1", "action": "EAT|REST|...", "target": "...", "thought": "..."}},
  {{"norn": "NornName2", ...}}
]

Valid actions: EAT REST PLAY TRAVEL APPROACH BREED SPEAK PUSH PICKUP DROP QUIET
Return ONLY the JSON array. No text before or after."""


def build_multi_perception(world) -> list[dict]:
    """Build perception dicts for all alive Norns."""
    perceptions = []
    for norn in world.norns:
        if not norn.alive:
            continue

        # Gather nearby Norn info
        nearby = []
        for other in world.norns:
            if other.name == norn.name or not other.alive:
                continue
            dx = abs(norn.x - other.x)
            dy = abs(norn.y - other.y)
            d = (dx**2 + dy**2) ** 0.5
            if d < 300:
                other_dna = other.agent.state.dna
                nearby.append({
                    "name": other.name,
                    "distance": round(d),
                    "species": other.species_id or "unknown",
                })

        p = {
            "tick": world.tick_count,
            "dna_traits": {
                "name": norn.name,
                **{k: getattr(norn.agent.state.dna, k, 0.5)
                   for k in ["curiosity", "sociability", "playfulness",
                            "aggression", "cautiousness", "intelligence"]}
            },
            "drives": {
                "hunger": norn.hunger, "fatigue": norn.fatigue,
                "boredom": norn.boredom, "loneliness": norn.loneliness,
                "fear": norn.fear, "sex_drive": norn.sex_drive,
            },
            "visible_objects": norn.visible_objects(world.objects),
            "nearby_norns": nearby,
            "weather": world.weather,
            "life_stage": norn.life_stage,
            "species_id": norn.species_id,
        }
        perceptions.append(p)
    return perceptions


def batch_llm_decide(world, model="deepseek-v4-pro") -> dict:
    """One LLM call decides actions for ALL Norns at once."""
    perceptions = build_multi_perception(world)
    if not perceptions:
        return {}

    # Build batch prompt
    blocks = []
    for p in perceptions:
        name = p["dna_traits"]["name"]
        prompt = format_perception_v2(p)
        blocks.append(f"=== {name} ===\n{prompt}\n")

    batch_prompt = BATCH_PROMPT_TEMPLATE.format(
        n=len(perceptions),
        perceptions="\n---\n".join(blocks),
    )

    try:
        result = subprocess.run(
            ["hermes", "-z", batch_prompt, "-m", model],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return {}

        response = result.stdout.strip()

        # Parse JSON array
        import re
        # Try direct
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try code block
            match = re.search(r"\[.*?\]", response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return {}
            else:
                return {}

        if not isinstance(data, list):
            return {}

        # Build name → action map
        actions = {}
        for item in data:
            if isinstance(item, dict) and "norn" in item and "action" in item:
                pkt = parse_llm_response(json.dumps(item))
                if pkt.valid:
                    actions[item["norn"]] = pkt.to_dict()
        return actions

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}


def parallel_llm_decide(world, model="deepseek-v4-pro", max_workers=4) -> dict:
    """N concurrent LLM calls — one per Norn."""
    perceptions = build_multi_perception(world)
    if not perceptions:
        return {}

    actions = {}

    def decide_one(perception: dict) -> tuple:
        name = perception["dna_traits"]["name"]
        prompt = format_perception_v2(perception)
        try:
            result = subprocess.run(
                ["hermes", "-z", prompt, "-m", model],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                pkt = parse_llm_response(result.stdout.strip())
                if pkt.valid:
                    return (name, pkt.to_dict())
        except Exception:
            pass
        return (name, {"action": "QUIET", "target": "", "valid": False})

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(decide_one, p): p for p in perceptions}
        for future in as_completed(futures):
            name, action = future.result()
            actions[name] = action

    return actions
