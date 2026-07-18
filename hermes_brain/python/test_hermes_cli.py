#!/usr/bin/env python3
"""
Hermes Norn — Hermes Agent CLI integration test.
Tests the full perception → LLM → action pipeline.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from norn_agent import format_perception, NornDNA
from genetics import NornGenome


# ── Hermes CLI: perception → action ──────────────────────────────

ACTIONS_JSON = """Valid actions (respond ONLY with a JSON object, no markdown, no backticks):
{
  "action": "EAT|APPROACH|PUSH|PICKUP|DROP|REST|PLAY|TRAVEL|BREED|SPEAK|QUIET",
  "target": "object name or direction (empty string if none)",
  "thought": "one sentence explaining why you chose this action"
}"""


def norn_think_hermes(perception: dict, model: str = "deepseek-v4-pro") -> dict:
    """Send perception to Hermes Agent CLI, get action back."""
    
    # Build the complete prompt
    dna = perception.get("dna_traits", {})
    
    system = f"""You are a Norn named {dna.get('name', 'Unnamed')} — a small alien creature in the game Creatures.
You live in the world of Albia. You are NOT an AI assistant — you ARE the creature.
Think like the creature would: follow your drives, personality, and instincts.

Your personality (from DNA):
- Curiosity: {dna.get('curiosity', 0.5):.0%} — how much you explore
- Aggression: {dna.get('aggression', 0.3):.0%} — how likely you are to fight
- Sociability: {dna.get('sociability', 0.6):.0%} — how much you seek others
- Playfulness: {dna.get('playfulness', 0.5):.0%} — how much you enjoy toys
- Cautiousness: {dna.get('cautiousness', 0.4):.0%} — how careful you are
- Intelligence: {dna.get('intelligence', 0.5):.0%} — how smart you are

CRITICAL RULES:
1. If you are hungry and see food → EAT it immediately
2. If you are tired → REST
3. If you see another Norn and are social → APPROACH them
4. If you are scared or in pain → TRAVEL away
5. Never explain your reasoning in text — put it in the "thought" field of the JSON
6. Respond ONLY with the JSON. No markdown formatting, no backticks."""

    user_msg = format_perception(perception)
    
    full_prompt = f"{system}\n\n{user_msg}\n\n{ACTIONS_JSON}"

    # Call Hermes CLI
    try:
        result = subprocess.run(
            ["hermes", "-z", full_prompt, "-m", model],
            capture_output=True, text=True, timeout=30,
        )
        
        response = result.stdout.strip()
        
        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        import re
        # ```json ... ```
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Just find any JSON object
        match = re.search(r'\{\s*"action"\s*:\s*"[^"]*".*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Return raw response for debugging
        return {"action": "QUIET", "target": "", "thought": f"[LLM raw: {response[:100]}...]"}
        
    except FileNotFoundError:
        return {"action": "QUIET", "target": "", "thought": "[Hermes CLI not found]"}
    except subprocess.TimeoutExpired:
        return {"action": "QUIET", "target": "", "thought": "[LLM timeout — falling back]"}


# ── Test Scenarios ───────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "Hungry Norn sees food",
        "perception": {
            "tick": 42,
            "dna_traits": {"name": "Nibbles", "curiosity": 0.5, "sociability": 0.5,
                          "playfulness": 0.5, "cautiousness": 0.5, "aggression": 0.3, "intelligence": 0.6},
            "drives": {"hunger": 0.9, "thirst": 0.3, "fatigue": 0.2, "boredom": 0.3,
                      "loneliness": 0.3, "fear": 0.1},
            "visible_objects": [
                {"type": "food", "name": "cheese", "distance": 40, "direction": "left"},
                {"type": "toy", "name": "ball", "distance": 200, "direction": "right"},
            ],
            "learned_words": {"cheese": "food"},
            "recent_memories": [],
            "life_stage": "child",
        },
        "expected_action": "EAT",
    },
    {
        "name": "Tired Norn should rest",
        "perception": {
            "tick": 100,
            "dna_traits": {"name": "Sleepy", "curiosity": 0.3, "sociability": 0.3,
                          "playfulness": 0.3, "cautiousness": 0.7, "aggression": 0.1, "intelligence": 0.5},
            "drives": {"hunger": 0.2, "thirst": 0.2, "fatigue": 0.95, "boredom": 0.2,
                      "loneliness": 0.2, "fear": 0.1},
            "visible_objects": [
                {"type": "food", "name": "apple", "distance": 100, "direction": "front"},
            ],
            "learned_words": {},
            "recent_memories": ["played with ball 50 ticks ago"],
            "life_stage": "adolescent",
        },
        "expected_action": "REST",
    },
    {
        "name": "Social Norn sees friend",
        "perception": {
            "tick": 200,
            "dna_traits": {"name": "Friendly", "curiosity": 0.5, "sociability": 0.95,
                          "playfulness": 0.7, "cautiousness": 0.2, "aggression": 0.05, "intelligence": 0.6},
            "drives": {"hunger": 0.2, "thirst": 0.2, "fatigue": 0.2, "boredom": 0.3,
                      "loneliness": 0.85, "fear": 0.1},
            "visible_objects": [
                {"type": "norn", "name": "Alice", "distance": 60, "direction": "right"},
                {"type": "food", "name": "berry", "distance": 150, "direction": "front"},
            ],
            "learned_words": {"Alice": "friend"},
            "recent_memories": [],
            "life_stage": "adult",
        },
        "expected_action": "APPROACH",
    },
    {
        "name": "Scared Norn should flee",
        "perception": {
            "tick": 300,
            "dna_traits": {"name": "Scaredy", "curiosity": 0.2, "sociability": 0.5,
                          "playfulness": 0.3, "cautiousness": 0.9, "aggression": 0.1, "intelligence": 0.5},
            "drives": {"hunger": 0.3, "thirst": 0.3, "fatigue": 0.2, "boredom": 0.2,
                      "loneliness": 0.3, "fear": 0.95, "pain": 0.1},
            "visible_objects": [
                {"type": "predator", "name": "grendel", "distance": 80, "direction": "front"},
            ],
            "learned_words": {"grendel": "danger"},
            "recent_memories": [],
            "life_stage": "child",
        },
        "expected_action": "TRAVEL",
    },
]


def run_tests():
    print("🧠 Hermes Agent CLI — Norn Brain Test\n")
    print("=" * 60)
    
    passed = 0
    total = len(SCENARIOS)
    
    for i, scenario in enumerate(SCENARIOS):
        print(f"\n📋 Scenario {i+1}/{total}: {scenario['name']}")
        print(f"   Expected: {scenario['expected_action']}")
        
        action = norn_think_hermes(scenario["perception"])
        
        actual = action.get("action", "???")
        thought = action.get("thought", "")
        target = action.get("target", "")
        
        ok = actual == scenario["expected_action"]
        status = "✅" if ok else "❌"
        
        print(f"   Got:      {actual} → {target}")
        print(f"   Thought:  {thought}")
        print(f"   Result:   {status}")
        
        if ok:
            passed += 1
    
    print(f"\n{'='*60}")
    print(f"📊 Results: {passed}/{total} scenarios passed")
    
    if passed == total:
        print("✅ All scenarios correct! Hermes Agent CLI is working as Norn brain.")
    elif passed >= total * 0.5:
        print("⚠️  Partial success — some scenarios need prompt tuning.")
    else:
        print("❌ Most scenarios failed — check prompt engineering.")


if __name__ == "__main__":
    run_tests()
