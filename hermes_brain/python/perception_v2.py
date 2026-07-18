#!/usr/bin/env python3
"""
Rich perception → prompt formatter for LLM-powered Norn brains.
Provides deep world context: life stages, weather, biochemistry, personalities, history.
"""
from typing import Optional

# ── Prompts ──────────────────────────────────────────────────────────

LIFE_STAGE_CONTEXT = {
    "baby": "You are a BABY Norn. You hatched recently. You are clumsy, curious about everything, and need frequent food and rest. You cannot breed yet. You learn words quickly.",
    "child": "You are a CHILD Norn. You are energetic, playful, and learning about the world. You can eat solid food, play with toys, and start socializing. You cannot breed yet.",
    "adolescent": "You are an ADOLESCENT Norn. You are becoming independent, exploring further, and discovering romantic interests. You CAN breed now.",
    "adult": "You are an ADULT Norn. You are at your peak — strong, capable, and experienced. You can breed, teach younger Norns, and survive independently.",
    "elder": "You are an ELDER Norn. You are wise but slowing down. You tire easily, need more rest, and prefer familiar places and routines. You remember many things.",
}

DRIVE_DESCRIPTIONS = {
    "hunger": ("🍽️ Hunger", "You need to find and eat food. Food objects you know: {known_foods}"),
    "thirst": ("💧 Thirst", "You need to drink water. Look for water sources or juicy fruits."),
    "fatigue": ("😴 Fatigue", "You are tired. REST to recover. If very tired, nothing else matters — sleep NOW."),
    "boredom": ("🎮 Boredom", "You crave stimulation. PLAY with toys, EXPLORE new areas, or APPROACH others for fun."),
    "loneliness": ("👤 Loneliness", "You crave social contact. APPROACH another Norn, or SPEAK to someone nearby. Social Norns suffer more from loneliness."),
    "fear": ("😱 Fear", "Something scares you. If fear is high, TRAVEL away from danger. Your cautiousness affects how easily you get scared."),
    "pain": ("🤕 Pain", "You are hurt. Find safety and REST. Pain overrides most other drives."),
    "anger": ("😤 Anger", "You feel aggressive. Aggressive Norns may PUSH others or act territorially."),
    "sex_drive": ("💕 Mating urge", "Your body wants to reproduce. Find another adult Norn and BREED with them."),
    "crowded": ("📦 Crowded", "Too many Norns nearby make you uncomfortable. Move to a less crowded area."),
}

WEATHER_EFFECTS = {
    "sunny": "☀️ Sunny weather — you feel energetic and happy. Plants grow normally.",
    "cloudy": "☁️ Cloudy weather — neutral conditions. Good for exploring.",
    "rainy": "🌧️ Rainy weather — you might feel a bit gloomy. Plants grow faster. Seek shelter if you dislike rain.",
}

WORLD_RULES = """RULES OF YOUR WORLD:
- Eating food reduces hunger. Different foods give different nutrition.
- Playing with toys reduces boredom. Some toys are more fun than others.
- Resting reduces fatigue dramatically. You CANNOT do anything else while resting.
- Approaching another Norn reduces loneliness (for both of you).
- Breeding requires being VERY close to another Norn with high sex drive.
- Travel moves you in a direction. Use it to explore or reach distant objects.
- If you cannot see what you need (food, toys, friends), TRAVEL to find it.
- Your DNA traits affect your behavior, but drives override personality.
- You can only do ONE action per turn. Choose wisely."""


def format_perception_v2(perception: dict) -> str:
    """
    Build a rich, contextual prompt for LLM-based Norn decision-making.
    Includes: life stage, weather, biochemistry, species, personality, history.
    """
    dna = perception.get("dna_traits", {})
    drives = perception.get("drives", {})
    visible = perception.get("visible_objects", [])
    words = perception.get("learned_words", {})
    memories = perception.get("recent_memories", [])
    biochem = perception.get("biochemistry", {})
    life_stage = perception.get("life_stage", "adult")
    weather = perception.get("weather", "sunny")
    tick = perception.get("tick", 0)
    species = perception.get("species_id", "Nornus_vulgaris")
    norn_name = dna.get("name", "Unnamed")
    age = perception.get("age", 0)
    fitness = perception.get("fitness", 0.0)
    nearby_norns = perception.get("nearby_norns", [])

    lines = []

    # ── IDENTITY ──
    lines.append(f"You are {norn_name}, a {species} Norn.")
    lines.append(f"Age: {age} ticks | Life stage: {life_stage.upper()}")
    lines.append("")
    lines.append(LIFE_STAGE_CONTEXT.get(life_stage, LIFE_STAGE_CONTEXT["adult"]))
    lines.append("")

    # ── WEATHER ──
    lines.append(WEATHER_EFFECTS.get(weather, WEATHER_EFFECTS["sunny"]))
    lines.append("")

    # ── PERSONALITY (DNA) ──
    lines.append("=== YOUR PERSONALITY ===")
    personality_traits = [
        ("Curiosity", dna.get("curiosity", 0.5), "How much you explore. High = seek new things. Low = stay near familiar."),
        ("Sociability", dna.get("sociability", 0.6), "How much you need others. High = approach Norns. Low = prefer solitude."),
        ("Playfulness", dna.get("playfulness", 0.5), "How much you enjoy toys. High = play often. Low = toys are boring."),
        ("Aggression", dna.get("aggression", 0.3), "How likely to fight or push. High = territorial. Low = peaceful."),
        ("Cautiousness", dna.get("cautiousness", 0.4), "How careful you are. High = avoid danger. Low = reckless explorer."),
        ("Intelligence", dna.get("intelligence", 0.5), "How smart you are. Affects learning speed and decision quality."),
    ]
    for name, val, desc in personality_traits:
        bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
        lines.append(f"  {name}: [{bar}] {val:.0%} — {desc}")

    lines.append("")
    
    # ── PHYSICAL STATE (drives) ──
    lines.append("=== HOW YOU FEEL PHYSICALLY ===")
    known_foods = ", ".join(w for w, m in words.items() if m == "food") or "unknown foods"
    
    for drive_name, (label, desc) in DRIVE_DESCRIPTIONS.items():
        val = drives.get(drive_name, 0)
        if val > 0.05:  # Only show non-trivial drives
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            urgency = ""
            if val > 0.8:
                urgency = " ⚠️ CRITICAL"
            elif val > 0.5:
                urgency = " ⚡ URGENT"
            desc_filled = desc.format(known_foods=known_foods)
            lines.append(f"  {label}: [{bar}] {val:.0%}{urgency}")
            if val > 0.3:
                lines.append(f"    → {desc_filled}")

    lines.append("")

    # ── BIOCHEMISTRY ──
    if biochem:
        lines.append("=== YOUR BODY CHEMISTRY ===")
        chem_labels = {
            "adrenaline": ("⚡ Adrenaline", "Fight-or-flight. High = you're alert, may flee or fight. Increases fear."),
            "cortisol": ("😰 Cortisol", "Stress hormone. High = you're stressed, immune system weakens."),
            "dopamine": ("😊 Dopamine", "Reward/pleasure. High = you feel good, learned something. Increases when playing/eating."),
            "oxytocin": ("💕 Oxytocin", "Bonding hormone. High = you feel attached to other Norns. Increases when socializing."),
            "endorphins": ("💪 Endorphins", "Pain relief. High = you feel less pain. Released when exercising."),
        }
        for chem, (chem_label, chem_desc) in chem_labels.items():
            val = biochem.get(chem, 0)
            if val > 0.05:
                bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                lines.append(f"  {chem_label}: [{bar}] {val:.0%} — {chem_desc}")
        lines.append("")

    # ── WHAT YOU SEE ──
    lines.append("=== WHAT YOU CAN SEE RIGHT NOW ===")
    if visible:
        for obj in visible:
            obj_type = obj.get("type", "?")
            obj_name = obj.get("name", "unknown")
            distance = obj.get("distance", "?")
            direction = obj.get("direction", "?")
            detail = obj.get("detail", "")

            type_emoji = {"food": "🍎", "toy": "🎯", "norn": "🧬", "plant": "🌱",
                          "predator": "🦖", "portal": "🌀", "tool": "🔧"}.get(obj_type, "❓")

            lines.append(f"  {type_emoji} {obj_name} ({obj_type}) — {direction}, {distance}px away")
            if detail:
                lines.append(f"     {detail}")
    else:
        lines.append("  Nothing interesting in sight. You should TRAVEL to explore.")

    lines.append("")

    # ── NEARBY NORNS ──
    if nearby_norns:
        lines.append("=== NORNS NEARBY ===")
        for nn in nearby_norns:
            nn_name = nn.get("name", "?")
            nn_distance = nn.get("distance", "?")
            nn_personality = nn.get("personality", "")
            nn_species = nn.get("species", "")
            lines.append(f"  🧬 {nn_name} ({nn_species}) — {nn_distance}px away")
            if nn_personality:
                lines.append(f"     Personality: {nn_personality}")
        lines.append("")

    # ── MEMORY ──
    lines.append("=== WHAT YOU REMEMBER ===")
    words_list = [f"{w}={m}" for w, m in words.items()]
    lines.append(f"  Words you know ({len(words_list)}): {', '.join(words_list) or 'nothing yet — you can learn!'}")

    if memories:
        lines.append(f"  Recent events:")
        for mem in memories[-5:]:
            lines.append(f"    • {mem}")
    else:
        lines.append("  You don't remember much yet. You're still young.")
    
    lines.append("")

    # ── FITNESS ──
    if fitness > 0:
        lines.append(f"=== YOUR FITNESS ===\n  Survival score: {fitness:.1f} (higher = better adapted to this world)")
        lines.append("")

    # ── WORLD RULES ──
    lines.append(WORLD_RULES)
    lines.append("")

    # ── DECISION PROMPT ──
    lines.append("=== YOUR DECISION ===")
    lines.append(f"You are at tick {tick}. What do you do RIGHT NOW?")
    lines.append("Think about your highest drives FIRST, then consider your personality.")
    lines.append("")
    lines.append("Respond with ONLY a JSON object (no explanation, no markdown, no backticks):")
    lines.append('{"action": "EAT|APPROACH|PUSH|PICKUP|DROP|REST|PLAY|TRAVEL|BREED|SPEAK|QUIET",')
    lines.append(' "target": "object name or direction (empty string if none)",')
    lines.append(' "thought": "one sentence — why you chose this action"}')

    return "\n".join(lines)


# ── Quick test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    perception = {
        "tick": 142,
        "age": 450,
        "species_id": "Nornus_curiosus",
        "life_stage": "adolescent",
        "weather": "rainy",
        "fitness": 12.5,
        "dna_traits": {
            "name": "Luna",
            "curiosity": 0.85, "sociability": 0.7,
            "playfulness": 0.9, "aggression": 0.1,
            "cautiousness": 0.3, "intelligence": 0.75,
        },
        "drives": {
            "hunger": 0.72, "thirst": 0.45, "fatigue": 0.20,
            "boredom": 0.85, "loneliness": 0.60, "fear": 0.05,
            "pain": 0.0, "anger": 0.1, "sex_drive": 0.25, "crowded": 0.1,
        },
        "biochemistry": {
            "adrenaline": 0.15, "cortisol": 0.2,
            "dopamine": 0.6, "oxytocin": 0.3,
        },
        "visible_objects": [
            {"type": "food", "name": "honey_drop", "distance": 55, "direction": "left"},
            {"type": "toy", "name": "puzzle_box", "distance": 40, "direction": "right",
             "detail": "A mysterious box that makes sounds when touched"},
            {"type": "norn", "name": "Orion", "distance": 120, "direction": "front",
             "detail": "Orion looks friendly and is playing with a ball"},
        ],
        "nearby_norns": [
            {"name": "Orion", "distance": 120, "species": "Nornus_curiosus",
             "personality": "curious=0.7, sociable=0.9, playful=0.8"},
        ],
        "learned_words": {"honey_drop": "food", "puzzle_box": "toy", "Orion": "friend"},
        "recent_memories": [
            "ate a carrot 30 ticks ago — crunchy and satisfying",
            "played with Orion 80 ticks ago — we had so much fun together!",
            "found puzzle_box 100 ticks ago — haven't figured it out yet",
        ],
    }
    
    prompt = format_perception_v2(perception)
    print(prompt)
    print(f"\n{'='*60}")
    print(f"Prompt length: {len(prompt)} chars, ~{len(prompt)//4} tokens")
