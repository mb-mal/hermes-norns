"""
VisionPerception — sends rendered world images to vision models (GPT-4V, Claude, LLaVA).
Returns structured JSON perception augmented by visual understanding.

The vision model can detect:
  - Spatial relationships ("grendel behind the bush")
  - Object groupings ("three Norns huddled together")
  - Path finding ("clear path to cheese, but obstacle between here and toy")
  - Danger assessment ("predator facing AWAY from me — safe to move")
"""
import base64
import io
import json
import subprocess
import tempfile

from PIL import Image
from world_renderer import WorldRenderer


VISION_PROMPT = """You are analyzing a top-down 2D view of the world of Albia, from the game Creatures.

The image shows:
- Green ground (darker = rainy, brighter = sunny)
- Colored circles with names = Norns (creatures). Life stage shown by color:
  Pink=baby, Blue=child, Green=adolescent, Gold=adult, Silver=elder
- Colored halo around Norns = mood (yellow=happy, gray=scared, red=angry, green=curious, purple=playful)
- Orange star shapes = food
- Gold diamond shapes = toys
- Red triangle shapes = predators (grendels)
- Purple circles = portals
- Tiny colored bar above Norn = hunger level (more red = hungrier)

Describe what you see. Then return a JSON perception object:

{
  "visible_objects": [
    {"type": "food|toy|norn|predator|portal|plant", "name": "...", "direction": "N|NE|E|SE|S|SW|W|NW", "distance": number, "detail": "what you notice about it"}
  ],
  "spatial_notes": "spatial relationships between objects",
  "danger_assessment": "safe|cautious|dangerous and why",
  "suggested_action": "what you think the Norn should do based on what you see",
  "interesting_observations": ["anything unusual or noteworthy"]
}

The center Norn is the one making this perception. Analyze what they can see from their position.
Return ONLY valid JSON, no explanation."""


def render_world_as_base64(world, norn, viewport_size=(512, 512)) -> str:
    """Render world centered on a Norn, return as base64 data URL."""
    renderer = WorldRenderer(world, viewport_size=viewport_size)
    img = renderer.render(center_x=norn.x, center_y=norn.y)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def render_world_to_file(world, norn, path: str, viewport_size=(512, 512)) -> str:
    """Render world centered on a Norn, save to PNG file. Returns path."""
    renderer = WorldRenderer(world, viewport_size=viewport_size)
    img = renderer.render(center_x=norn.x, center_y=norn.y)
    img.save(path, format="PNG")
    return path


def vision_perceive_hermes(world, norn, model="deepseek-v4-pro") -> dict:
    """
    Send rendered world view to Hermes for vision analysis.
    Hermes will see the image and return structured perception.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img_path = f.name

    render_world_to_file(world, norn, img_path)

    # Use the vision_analyze tool equivalent via Hermes
    # Hermes -z prompt reads the image from the path
    prompt = f"{VISION_PROMPT}\n\nThe Norn at the center of this view is named {norn.name} (stage: {norn.life_stage}, mood: {norn.mood}). What do they see?"

    # We can't easily pass images to hermes -z, so we use a different approach:
    # For now, return the structured text-based perception + the image path for reference
    text_perception = {
        "tick": world.tick_count,
        "norn": norn.name,
        "rendered_image": img_path,
        "note": "Vision perception requires image-capable model (GPT-4V, Claude, LLaVA). Use vision_analyze tool.",
    }

    # Merge with standard drives/objects
    text_perception["drives"] = {
        "hunger": norn.hunger, "fatigue": norn.fatigue,
        "boredom": norn.boredom, "loneliness": norn.loneliness,
        "fear": norn.fear,
    }
    text_perception["visible_objects"] = norn.visible_objects(world.objects)
    text_perception["weather"] = world.weather

    return text_perception


# ── Standalone test ───────────────────────────────────────────────

if __name__ == "__main__":
    from world_sim import World, WorldObject

    world = World()
    world.weather_timer = 999
    world.weather = "sunny"

    alice = world.add_norn("Alice", 200, 200)
    alice.life_stage = "adult"
    alice.mood = "happy"

    bob = world.add_norn("Bob", 260, 220)
    bob.life_stage = "child"
    bob.mood = "curious"

    world.spawn_food("cheese", 230, 190, 30)
    world.spawn_food("apple", 150, 240, 40)
    world.objects.append(WorldObject("Grendel", "predator", 350, 150, danger_level=0.9))

    # Render
    img_path = render_world_to_file(world, alice, "/tmp/norn_vision_test.png")
    print(f"Rendered: {img_path}")

    print("\nIf you had a vision model, you'd send this image with the prompt.")
    print(f"Prompt preview: {VISION_PROMPT[:200]}...")

    # Show perception
    p = vision_perceive_hermes(world, alice)
    print(f"\nPerception: {json.dumps(p, indent=2)[:500]}...")
