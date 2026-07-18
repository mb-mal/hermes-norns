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
    """Simple rule-based fallback (no LLM needed)."""
    drives = perception.get("drives", {})
    visible = perception.get("visible_objects", [])
    dna = perception.get("dna_traits", {})

    # Priority order
    if drives.get("pain", 0) > 0.7:
        return {"action": "TRAVEL", "target": "away", "thought": "I'm in pain — need to escape!"}

    if drives.get("fear", 0) > 0.6:
        return {"action": "TRAVEL", "target": "away", "thought": "I'm scared — running away!"}

    if drives.get("fatigue", 0) > 0.7:
        return {"action": "REST", "target": "", "thought": "So tired... need sleep"}

    if drives.get("hunger", 0) > 0.5:
        food = [o for o in visible if o.get("type") == "food"]
        if food:
            target = min(food, key=lambda o: o.get("distance", 999))
            return {"action": "EAT", "target": target["name"], "thought": "Food! Eating now."}
        return {"action": "TRAVEL", "target": "forward", "thought": "Hungry — looking for food"}

    if drives.get("boredom", 0) > 0.5 and dna.get("playfulness", 0.5) > 0.4:
        toys = [o for o in visible if o.get("type") == "toy"]
        if toys:
            target = min(toys, key=lambda o: o.get("distance", 999))
            return {"action": "PLAY", "target": target["name"], "thought": "Bored — let's play!"}

    if drives.get("loneliness", 0) > 0.5 and dna.get("sociability", 0.5) > 0.4:
        norns = [o for o in visible if o.get("type") == "norn"]
        if norns:
            target = min(norns, key=lambda o: o.get("distance", 999))
            return {"action": "APPROACH", "target": target["name"], "thought": "I see another Norn! Going to say hi."}

    if drives.get("sex_drive", 0) > 0.6:
        norns = [o for o in visible if o.get("type") == "norn"]
        if norns:
            return {"action": "BREED", "target": norns[0]["name"], "thought": "Time to find a mate!"}

    if dna.get("curiosity", 0.5) > 0.6:
        interesting = [o for o in visible if o.get("type") not in ("food", "toy", "norn")]
        if interesting:
            return {"action": "APPROACH", "target": interesting[0]["name"], "thought": "What's that? Let me check it out."}

    return {"action": "QUIET", "target": "", "thought": "Nothing urgent. Just resting."}


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
