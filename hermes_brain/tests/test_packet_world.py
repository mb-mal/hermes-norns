"""
TDD tests for packet → world effects.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from action_packet import NornActionPacket
from world_sim import World


class TestPacketWorldEffects:

    def test_say_heard_by_nearby_norns(self):
        """Speech is stored in nearby Norns' memories, far Norns don't hear."""
        world = World()
        world.weather_timer = 999
        speaker = world.add_norn("Speaker", 100, 100)
        listener = world.add_norn("Listener", 130, 100)   # 30px — hears
        far = world.add_norn("Far", 900, 900)             # too far

        packet = NornActionPacket.from_dict(
            {"action": "SPEAK", "say": "food here"})
        world.apply_packet_effects(speaker, packet)

        assert any("food here" in m for m in listener.agent.state.memories)
        assert not any("food here" in m for m in far.agent.state.memories)

    def test_learn_adds_words(self):
        """Learned words go into the Norn's vocabulary."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Student", 100, 100)

        packet = NornActionPacket.from_dict(
            {"action": "QUIET", "learn": {"cheese": "food", "ball": "toy"}})
        world.apply_packet_effects(norn, packet)

        assert norn.agent.state.learned_words.get("cheese") == "food"
        assert norn.agent.state.learned_words.get("ball") == "toy"

    def test_mood_stored_on_body(self):
        """Mood from packet is visible on the Norn body."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Moody", 100, 100)

        packet = NornActionPacket.from_dict({"action": "PLAY", "mood": "excited"})
        world.apply_packet_effects(norn, packet)

        assert norn.mood == "excited"

    def test_social_updates_relationships(self):
        """Social signal updates the relationship map."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Friendly", 100, 100)
        world.add_norn("Alice", 130, 100)

        packet = NornActionPacket.from_dict({
            "action": "APPROACH", "target": "Alice",
            "social": {"toward": "Alice", "feeling": "friendly"}})
        world.apply_packet_effects(norn, packet)

        assert norn.relationships.get("Alice") == "friendly"

    def test_invalid_packet_no_side_effects(self):
        """Invalid (coerced) packets don't produce speech/learning effects."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Safe", 100, 100)
        listener = world.add_norn("Nearby", 120, 100)

        packet = NornActionPacket.from_dict({"action": "HACK_WORLD", "say": "exploit"})
        world.apply_packet_effects(norn, packet)

        assert not any("exploit" in m for m in listener.agent.state.memories)
