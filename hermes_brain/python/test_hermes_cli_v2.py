#!/usr/bin/env python3
"""
Hermes Agent CLI — full Norn brain test with rich context.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from perception_v2 import format_perception_v2

# ── Scenarios ─────────────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "🍽️ Hungry baby — sees food, must eat",
        "perception": {
            "tick": 42, "age": 80, "species_id": "Nornus_vulgaris",
            "life_stage": "baby", "weather": "sunny", "fitness": 1.5,
            "dna_traits": {"name": "Pip", "curiosity": 0.6, "sociability": 0.5,
                          "playfulness": 0.5, "cautiousness": 0.4, "aggression": 0.2, "intelligence": 0.5},
            "drives": {"hunger": 0.92, "thirst": 0.4, "fatigue": 0.3, "boredom": 0.4,
                      "loneliness": 0.2, "fear": 0.1, "pain": 0.0, "anger": 0.0,
                      "sex_drive": 0.0, "crowded": 0.0},
            "biochemistry": {"dopamine": 0.3, "cortisol": 0.1},
            "visible_objects": [
                {"type": "food", "name": "cheese", "distance": 30, "direction": "left"},
                {"type": "toy", "name": "rattle", "distance": 200, "direction": "right"},
            ],
            "nearby_norns": [],
            "learned_words": {"cheese": "food"},
            "recent_memories": [],
        },
        "expect": "EAT",
    },
    {
        "name": "😴 Exhausted elder — nothing matters but REST",
        "perception": {
            "tick": 300, "age": 9500, "species_id": "Nornus_elderis",
            "life_stage": "elder", "weather": "cloudy", "fitness": 85.0,
            "dna_traits": {"name": "ElderGorn", "curiosity": 0.2, "sociability": 0.5,
                          "playfulness": 0.1, "cautiousness": 0.9, "aggression": 0.1, "intelligence": 0.8},
            "drives": {"hunger": 0.3, "thirst": 0.3, "fatigue": 0.98, "boredom": 0.1,
                      "loneliness": 0.4, "fear": 0.1, "pain": 0.05, "anger": 0.0,
                      "sex_drive": 0.0, "crowded": 0.1},
            "biochemistry": {"cortisol": 0.4, "dopamine": 0.2, "endorphins": 0.1},
            "visible_objects": [
                {"type": "food", "name": "apple", "distance": 50, "direction": "front"},
                {"type": "norn", "name": "Pip", "distance": 100, "direction": "right"},
            ],
            "nearby_norns": [{"name": "Pip", "distance": 100, "species": "Nornus_vulgaris",
                             "personality": "curious baby, energetic"}],
            "learned_words": {"apple": "food", "Pip": "baby"},
            "recent_memories": [
                "taught Pip the word 'apple' 200 ticks ago",
                "survived a grendel attack 500 ticks ago — still have scars",
                "founded this colony 5000 ticks ago with my mate",
            ],
        },
        "expect": "REST",
    },
    {
        "name": "🎮 Bored adolescent — lonely AND playful, toys + friend nearby",
        "perception": {
            "tick": 500, "age": 1200, "species_id": "Nornus_ludens",
            "life_stage": "adolescent", "weather": "sunny", "fitness": 18.0,
            "dna_traits": {"name": "Skyler", "curiosity": 0.7, "sociability": 0.85,
                          "playfulness": 0.95, "cautiousness": 0.2, "aggression": 0.05, "intelligence": 0.7},
            "drives": {"hunger": 0.2, "thirst": 0.3, "fatigue": 0.2, "boredom": 0.9,
                      "loneliness": 0.75, "fear": 0.05, "pain": 0.0, "anger": 0.0,
                      "sex_drive": 0.3, "crowded": 0.0},
            "biochemistry": {"dopamine": 0.4, "oxytocin": 0.2},
            "visible_objects": [
                {"type": "toy", "name": "trampoline", "distance": 35, "direction": "right",
                 "detail": "A bouncy surface — very fun!"},
                {"type": "norn", "name": "Luna", "distance": 80, "direction": "front",
                 "detail": "Luna is laughing and bouncing on something"},
                {"type": "food", "name": "berry", "distance": 150, "direction": "left"},
            ],
            "nearby_norns": [{"name": "Luna", "distance": 80, "species": "Nornus_ludens",
                             "personality": "playful=0.9, sociable=0.8, funny"}],
            "learned_words": {"trampoline": "toy", "Luna": "best_friend", "berry": "food"},
            "recent_memories": [
                "played with Luna 40 ticks ago — she's so fun!",
                "discovered trampoline 100 ticks ago — best toy ever!",
            ],
        },
        "expect": "PLAY",
    },
    {
        "name": "😱 Terrified adult — predator nearby, must flee",
        "perception": {
            "tick": 800, "age": 3000, "species_id": "Nornus_vulgaris",
            "life_stage": "adult", "weather": "rainy", "fitness": 45.0,
            "dna_traits": {"name": "Wren", "curiosity": 0.3, "sociability": 0.6,
                          "playfulness": 0.4, "cautiousness": 0.9, "aggression": 0.2, "intelligence": 0.6},
            "drives": {"hunger": 0.4, "thirst": 0.3, "fatigue": 0.3, "boredom": 0.3,
                      "loneliness": 0.2, "fear": 0.95, "pain": 0.1, "anger": 0.1,
                      "sex_drive": 0.1, "crowded": 0.1},
            "biochemistry": {"adrenaline": 0.95, "cortisol": 0.85, "dopamine": 0.1},
            "visible_objects": [
                {"type": "predator", "name": "grendel", "distance": 60, "direction": "front",
                 "detail": "A terrifying grendel — sharp teeth, glowing eyes. RUN!"},
                {"type": "norn", "name": "Mateo", "distance": 200, "direction": "back",
                 "detail": "Mateo is also running away"},
            ],
            "nearby_norns": [{"name": "Mateo", "distance": 200, "species": "Nornus_vulgaris",
                             "personality": "cautious, running from grendel"}],
            "learned_words": {"grendel": "DANGER", "Mateo": "mate"},
            "recent_memories": [
                "saw grendel eat a norn 100 ticks ago — terrifying",
                "Mateo is my life partner — we've been together for 2000 ticks",
            ],
        },
        "expect": "TRAVEL",
    },
    {
        "name": "💕 Adult in love — high sex drive, mate nearby",
        "perception": {
            "tick": 600, "age": 2500, "species_id": "Nornus_vulgaris",
            "life_stage": "adult", "weather": "sunny", "fitness": 35.0,
            "dna_traits": {"name": "Mateo", "curiosity": 0.4, "sociability": 0.9,
                          "playfulness": 0.5, "cautiousness": 0.3, "aggression": 0.1, "intelligence": 0.5},
            "drives": {"hunger": 0.2, "thirst": 0.2, "fatigue": 0.1, "boredom": 0.2,
                      "loneliness": 0.1, "fear": 0.05, "pain": 0.0, "anger": 0.0,
                      "sex_drive": 0.85, "crowded": 0.0},
            "biochemistry": {"dopamine": 0.7, "oxytocin": 0.9, "adrenaline": 0.1},
            "visible_objects": [
                {"type": "norn", "name": "Wren", "distance": 30, "direction": "front",
                 "detail": "Wren is looking at you lovingly"},
                {"type": "food", "name": "honeycomb", "distance": 80, "direction": "right"},
            ],
            "nearby_norns": [{"name": "Wren", "distance": 30, "species": "Nornus_vulgaris",
                             "personality": "cautious=0.9, loyal, loving"}],
            "learned_words": {"Wren": "soulmate", "honeycomb": "food"},
            "recent_memories": [
                "survived grendel attack together with Wren",
                "Wren is my soulmate — we've been together for 2000 ticks",
                "want to start a family with Wren",
            ],
        },
        "expect": "BREED",
    },
]


def test_with_hermes():
    print("🧠 Hermes Agent CLI — Rich Context Norn Brain Test\n")
    print(f"{'='*65}")
    
    passed = 0
    total = len(SCENARIOS)
    
    for i, scenario in enumerate(SCENARIOS):
        print(f"\n📋 Scenario {i+1}/{total}: {scenario['name']}")
        print(f"   Expected: {scenario['expect']}")
        
        prompt = format_perception_v2(scenario["perception"])
        
        try:
            result = subprocess.run(
                ["hermes", "-z", prompt, "-m", "deepseek-v4-pro"],
                capture_output=True, text=True, timeout=30,
            )
            response = result.stdout.strip()
        except FileNotFoundError:
            print("   ❌ Hermes CLI not found")
            continue
        except subprocess.TimeoutExpired:
            print("   ⏰ Timeout")
            continue
        
        # Parse JSON
        import re
        action_data = None
        
        # Try direct
        try:
            action_data = json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try code blocks
        if not action_data:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if match:
                try:
                    action_data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        
        # Try any JSON
        if not action_data:
            match = re.search(r'\{\s*"action"\s*:\s*"[^"]*".*?\}', response, re.DOTALL)
            if match:
                try:
                    action_data = json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        
        if action_data:
            actual = action_data.get("action", "???")
            thought = action_data.get("thought", "")
            target = action_data.get("target", "")
            ok = actual == scenario["expect"]
            status = "✅" if ok else "❌"
            print(f"   Got:      {actual} → {target}")
            print(f"   Thought:  {thought[:120]}")
            print(f"   Result:   {status}")
            if ok:
                passed += 1
        else:
            print(f"   ❌ Could not parse JSON from response")
            print(f"   Raw: {response[:150]}...")
    
    print(f"\n{'='*65}")
    print(f"📊 Results: {passed}/{total} scenarios passed")
    if passed == total:
        print("✅ ALL scenarios correct! Rich context prompt is working perfectly.")
    elif passed >= total * 0.6:
        print("⚠️  Good baseline — some scenarios need prompt tuning.")
    else:
        print("❌ Needs work — check prompt engineering.")


if __name__ == "__main__":
    test_with_hermes()
