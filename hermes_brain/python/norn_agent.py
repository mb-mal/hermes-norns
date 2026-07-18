#!/usr/bin/env python3
"""
Hermes Norn Agent — LLM-powered creature brain.
Replaces the classic neural network brain (c2eBrain) with a Hermes Agent.

Protocol:
  Reads JSON perception from stdin, writes JSON action to stdout.
  One line = one tick cycle.

Usage:
  echo '{"tick": 0, "drives": {"hunger": 0.9}, ...}' | python3 norn_agent.py
"""

import json
import sys
import os
import random
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────

@dataclass
class NornDNA:
    """Personality traits derived from creature genetics."""
    name: str = "Unnamed"
    curiosity: float = 0.5
    aggression: float = 0.3
    sociability: float = 0.6
    intelligence: float = 0.5
    playfulness: float = 0.5
    cautiousness: float = 0.4

@dataclass
class NornState:
    """Mutable state of a single Norn."""
    dna: NornDNA = field(default_factory=NornDNA)
    learned_words: dict = field(default_factory=dict)
    memories: list = field(default_factory=list)  # last N events
    favorite_foods: list = field(default_factory=list)
    feared_objects: list = field(default_factory=list)

# ── Action Space ────────────────────────────────────────────────

ACTIONS = [
    "APPROACH <object>",
    "EAT <object>",
    "PUSH <object>",
    "PICKUP <object>",
    "DROP",
    "SPEAK <word>",
    "REST",
    "PLAY <object>",
    "TRAVEL <direction>",
    "BREED <norn>",
    "QUIET",
]

DIRECTIONS = ["left", "right", "up", "down", "forward"]

# ── Perception → Prompt ─────────────────────────────────────────

def format_perception(perception: dict) -> str:
    """Convert raw perception JSON into a natural-language prompt."""
    dna = perception.get("dna_traits", {})
    drives = perception.get("drives", {})
    visible = perception.get("visible_objects", [])
    words = perception.get("learned_words", {})
    memories = perception.get("recent_memories", [])
    biochem = perception.get("biochemistry", {})

    # Drive descriptions
    drive_lines = []
    for name, val in drives.items():
        if val > 0.7:
            drive_lines.append(f"  - VERY {name}: {val:.0%}")
        elif val > 0.4:
            drive_lines.append(f"  - {name}: {val:.0%}")

    # Visible objects
    obj_lines = []
    for obj in visible:
        direction = obj.get("direction", "somewhere")
        obj_lines.append(f"  - {obj.get('name', 'something')} ({obj.get('type', 'unknown')}) — {direction}, {obj.get('distance', '?')}px away")

    prompt = f"""You are a Norn named {dna.get('name', 'Unnamed')}. You are a small creature living in the world of Albia.

=== YOUR PERSONALITY (from DNA) ===
- Curiosity: {dna.get('curiosity', 0.5):.0%}
- Aggression: {dna.get('aggression', 0.3):.0%}
- Sociability: {dna.get('sociability', 0.6):.0%}
- Playfulness: {dna.get('playfulness', 0.5):.0%}
- Cautiousness: {dna.get('cautiousness', 0.4):.0%}
- Intelligence: {dna.get('intelligence', 0.5):.0%}

=== HOW YOU FEEL ===
{chr(10).join(drive_lines) if drive_lines else '  You feel content and balanced.'}

=== WHAT YOU CAN SEE ===
{chr(10).join(obj_lines) if obj_lines else '  Nothing interesting nearby.'}

=== WHAT YOU KNOW ===
Words: {', '.join(f'{w}={m}' for w,m in words.items()) if words else 'none yet'}
Recent: {'; '.join(memories[-3:]) if memories else 'nothing memorable'}

=== DECISION ===
Choose ONE action. You are a simple creature — act on your drives and personality.
Respond ONLY with a JSON object: {{"action": "EAT", "target": "carrot", "thought": "I see food and I'm hungry"}}

Valid actions:
{chr(10).join('  - ' + a for a in ACTIONS)}
"""
    return prompt


def rule_based_action(perception: dict) -> dict:
    """Rule-based agent with proportional action selection."""
    drives = perception.get("drives", {})
    visible = perception.get("visible_objects", [])
    dna = perception.get("dna_traits", {})

    # Build weighted action candidates
    candidates = []  # (weight, action_dict)

    # PAIN / FEAR — emergency override
    if drives.get("pain", 0) > 0.7:
        return {"action": "TRAVEL", "target": "away", "thought": "I'm in pain — escaping!"}
    if drives.get("fear", 0) > 0.6:
        return {"action": "TRAVEL", "target": "away", "thought": "Scared — running away!"}

    # FATIGUE — high priority
    if drives.get("fatigue", 0) > 0.6:
        candidates.append((drives["fatigue"] * 2.0, {"action": "REST", "target": "", "thought": "So tired... need sleep"}))

    # HUNGER
    food = [o for o in visible if o.get("type") == "food"]
    if food and drives.get("hunger", 0) > 0.2:
        target = min(food, key=lambda o: o.get("distance", 999))
        w = drives.get("hunger", 0) * 1.5
        candidates.append((w, {"action": "EAT", "target": target["name"], "thought": "Eating nearby food."}))
    elif drives.get("hunger", 0) > 0.3:
        candidates.append((0.3, {"action": "TRAVEL", "target": "forward", "thought": "Hungry — looking for food"}))

    # PLAY
    toys = [o for o in visible if o.get("type") == "toy"]
    if toys and dna.get("playfulness", 0.3) > 0.2:
        target = min(toys, key=lambda o: o.get("distance", 999))
        w = max(drives.get("boredom", 0), 0.3) * dna.get("playfulness", 0.5)
        candidates.append((w, {"action": "PLAY", "target": target["name"], "thought": "Let's play!"}))

    # SOCIALIZE
    norns_visible = [o for o in visible if o.get("type") == "norn"]
    if norns_visible and dna.get("sociability", 0.3) > 0.2:
        target = min(norns_visible, key=lambda o: o.get("distance", 999))
        w = max(drives.get("loneliness", 0), 0.3) * dna.get("sociability", 0.5)
        candidates.append((w, {"action": "APPROACH", "target": target["name"], "thought": "Going to say hi!"}))

    # BREED
    if norns_visible and drives.get("sex_drive", 0) > 0.5:
        candidates.append((0.4, {"action": "BREED", "target": norns_visible[0]["name"], "thought": "Time to mate!"}))

    # EXPLORE (curiosity)
    interesting = [o for o in visible if o.get("type") not in ("food", "toy", "norn")]
    if interesting and dna.get("curiosity", 0.3) > 0.3:
        w = dna.get("curiosity", 0.5) * 0.5
        candidates.append((w, {"action": "APPROACH", "target": interesting[0]["name"], "thought": "What's that?"}))

    # Default: travel randomly or rest
    candidates.append((0.15, {"action": "QUIET", "target": "", "thought": "Nothing urgent. Resting."}))

    if not candidates:
        return {"action": "QUIET", "target": "", "thought": "..."}

    # Weighted random selection
    total = sum(w for w, _ in candidates)
    r = random.uniform(0, total)
    cumulative = 0
    for w, action in candidates:
        cumulative += w
        if r <= cumulative:
            return action

    return candidates[-1][1]


# ── Main Agent Loop ─────────────────────────────────────────────

class NornAgent:
    """A single Norn brain powered by Hermes Agent or rule-based logic."""

    def __init__(self, use_llm: bool = False, model: str = "llama3"):
        self.use_llm = use_llm
        self.model = model
        self.state = NornState()
        self.tick_count = 0

    def perceive(self, perception: dict) -> dict:
        """Process perception and return action."""
        self.tick_count = perception.get("tick", self.tick_count)

        # Update DNA if provided
        if "dna_traits" in perception:
            dna = self.state.dna
            for k, v in perception["dna_traits"].items():
                if hasattr(dna, k):
                    setattr(dna, k, v)

        # Update learned words
        if "learned_words" in perception:
            self.state.learned_words.update(perception["learned_words"])

        # Add to memory
        if "recent_memories" in perception:
            self.state.memories.extend(perception["recent_memories"])
            self.state.memories = self.state.memories[-50:]  # cap at 50

        # Decision
        if self.use_llm:
            action = self._llm_decision(perception)
        else:
            action = rule_based_action(perception)

        # Store in memory
        self.state.memories.append(
            f"tick {self.tick_count}: {action['action']} {action.get('target', '')} — {action.get('thought', '')}"
        )
        self.state.memories = self.state.memories[-50:]

        return action

    def _llm_decision(self, perception: dict) -> dict:
        """Use an LLM (via Hermes Agent CLI) to decide."""
        prompt = format_perception({**perception, "dna_traits": self.state.dna.__dict__})
        
        # Try Hermes Agent CLI first
        try:
            import subprocess
            result = subprocess.run(
                ["hermes", "agent", "--prompt", prompt, "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

        # Fallback: use llama-cpp-python if available
        try:
            from llama_cpp import Llama
            # This would need model loading — simplified for now
            pass
        except ImportError:
            pass

        # Ultimate fallback: rule-based
        return rule_based_action(perception)


def main():
    """CLI entry point: read JSON line from stdin, write JSON line to stdout."""
    agent = NornAgent(use_llm=False)  # default to rule-based for now

    print("🧠 Hermes Norn Agent ready (rule-based mode)", file=sys.stderr)
    print("   Waiting for perception JSON on stdin...", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            perception = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"error": "invalid json"}), flush=True)
            continue

        action = agent.perceive(perception)
        print(json.dumps(action), flush=True)


if __name__ == "__main__":
    main()
