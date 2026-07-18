"""
Extended edge-case and exception tests for NornActionPacket, parser, and world integration.
Covers: Unicode, injections, malformed input, concurrency, limits, nulls, and adversarial inputs.
"""
import sys, json, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from action_packet import NornActionPacket, parse_llm_response
from world_sim import World


# ═══════════════════════════════════════════════════════════════
# PARSER — adversarial & edge inputs
# ═══════════════════════════════════════════════════════════════

class TestParserEdgeCases:

    def test_unicode_emoji_in_fields(self):
        p = parse_llm_response('{"action":"EAT","target":"🍎","thought":"вкусно 🎉😋"}')
        assert p.action == "EAT"
        assert p.target == "🍎"
        assert "вкусно" in p.thought
        assert p.valid

    def test_extremely_long_response(self):
        """Multi-kilobyte response — only valid JSON matters."""
        long = 'x' * 10000 + '{"action":"REST","thought":"tired"}' + 'y' * 10000
        p = parse_llm_response(long)
        assert p.action == "REST"
        assert p.valid

    def test_only_braces_no_action(self):
        """{} with no action key → invalid."""
        p = parse_llm_response("{}")
        assert p.action == "QUIET"
        assert not p.valid

    def test_json_with_action_as_number(self):
        """action: 123 → coerced to QUIET."""
        p = parse_llm_response('{"action":123}')
        assert p.action == "QUIET"

    def test_json_with_action_as_null(self):
        p = parse_llm_response('{"action":null}')
        assert p.action == "QUIET"

    def test_json_with_action_as_list(self):
        p = parse_llm_response('{"action":["EAT"]}')
        assert p.action == "QUIET"

    def test_escaped_quotes_in_thought(self):
        p = parse_llm_response('{"action":"EAT","thought":"I said \\"hello\\" to Luna"}')
        assert p.action == "EAT"
        assert '"hello"' in p.thought

    def test_invisible_unicode_characters(self):
        """Zero-width spaces in action → becomes QUIET."""
        p = parse_llm_response('{"action":"REST\\u200b","thought":"tired"}')
        assert p.action == "QUIET"  # REST\\u200b ≠ REST, not in whitelist
        assert not p.valid

    def test_binary_null_byte_in_response(self):
        """Null bytes shouldn't crash the parser."""
        p = parse_llm_response('{"action":"EAT","target":"cheese"}' + '\x00')
        assert p.action == "EAT"

    def test_deeply_nested_social_field(self):
        """Nested objects in social shouldn't break extraction."""
        txt = '{"action":"BREED","target":"Wren","social":{"toward":"Wren","feeling":"loving","extra":{"deep":"value"}}}'
        p = parse_llm_response(txt)
        assert p.action == "BREED"
        assert p.social["feeling"] == "loving"

    def test_multiple_json_candidates_picks_first_valid(self):
        """First candidate invalid → parser tries next."""
        txt = '{"action":"HACK","target":"x"}\n{"action":"EAT","target":"apple"}'
        p = parse_llm_response(txt)
        # Both are found as candidates. HACK → QUIET (invalid).
        # Parser returns the first VALID candidate (EAT).
        assert p.action == "EAT"
        assert p.valid

    def test_newline_in_string_value(self):
        """JSON with literal newlines in strings (some models emit this)."""
        txt = '{"action":"SPEAK","say":"hello\\nworld"}'
        p = parse_llm_response(txt)
        assert p.action == "SPEAK"

    def test_json_inside_text_after_explanation(self):
        """LLM explains THEN gives JSON."""
        txt = 'As a norn, I feel hungry and there is cheese nearby.\n\nAction: {"action":"EAT","target":"cheese","thought":"hungry"}'
        p = parse_llm_response(txt)
        assert p.action == "EAT"

    def test_only_spaces_and_newlines(self):
        p = parse_llm_response("\n  \n  \n")
        assert p.action == "QUIET"
        assert not p.valid

    def test_non_string_input_list(self):
        """If somehow a list is passed (e.g., from a broken adapter)."""
        # The function signature expects string, but just in case
        p = parse_llm_response(str(["action", "EAT"]))
        assert p.action == "QUIET"


# ═══════════════════════════════════════════════════════════════
# VALIDATOR — adversarial field inputs
# ═══════════════════════════════════════════════════════════════

class TestValidatorEdgeCases:

    def test_action_empty_string(self):
        p = NornActionPacket.from_dict({"action": ""})
        assert p.action == "QUIET"
        assert not p.valid

    def test_action_whitespace_only(self):
        p = NornActionPacket.from_dict({"action": "   "})
        assert p.action == "QUIET"
        assert not p.valid

    def test_action_with_extra_spaces(self):
        """'  EAT  ' → 'EAT' after strip."""
        p = NornActionPacket.from_dict({"action": "  eat  "})
        assert p.action == "EAT"
        assert p.valid

    def test_target_is_number_converted_to_string(self):
        p = NornActionPacket.from_dict({"action": "EAT", "target": 42})
        assert p.target == "42"

    def test_target_is_dict_converted_to_string(self):
        p = NornActionPacket.from_dict({"action": "EAT", "target": {"name": "cheese"}})
        assert isinstance(p.target, str)

    def test_mood_as_int(self):
        p = NornActionPacket.from_dict({"action": "REST", "mood": 123})
        assert p.mood == "calm"

    def test_mood_as_list(self):
        p = NornActionPacket.from_dict({"action": "REST", "mood": ["happy"]})
        assert p.mood == "calm"

    def test_learn_as_string(self):
        p = NornActionPacket.from_dict({"action": "QUIET", "learn": "not a dict"})
        assert p.learn == {}

    def test_learn_as_list(self):
        p = NornActionPacket.from_dict({"action": "QUIET", "learn": [1, 2, 3]})
        assert p.learn == {}

    def test_learn_with_injection_attempt(self):
        """LLM tries to inject SQL via word meaning — stored, harmless, length-capped."""
        p = NornActionPacket.from_dict({
            "action": "QUIET",
            "learn": {"cheese": "'; DROP TABLE creatures; --"}
        })
        # String is 27 chars — under 30 cap, not truncated.
        # But it's just a stored string in memory, never executed.
        assert len(p.learn["cheese"]) <= 30
        assert "cheese" in p.learn

    def test_social_toward_is_number(self):
        p = NornActionPacket.from_dict({"action": "APPROACH",
            "social": {"toward": 123, "feeling": "friendly"}})
        assert p.social["toward"] == "123"

    def test_social_feeling_as_list(self):
        p = NornActionPacket.from_dict({"action": "APPROACH",
            "social": {"toward": "Alice", "feeling": ["friendly"]}})
        assert p.social["feeling"] == "neutral"

    def test_social_with_no_toward_field(self):
        p = NornActionPacket.from_dict({"action": "APPROACH",
            "social": {"feeling": "friendly"}})
        assert p.social == {}

    def test_social_with_no_feeling_field(self):
        p = NornActionPacket.from_dict({"action": "APPROACH",
            "social": {"toward": "Alice"}})
        assert p.social["feeling"] == "neutral"

    def test_say_with_control_characters(self):
        p = NornActionPacket.from_dict({"action": "SPEAK", "say": "hello\x07world"})
        assert "hello" in p.say

    def test_all_fields_simultaneously_insane_values(self):
        """Extreme adversarial: every field is wrong type."""
        p = NornActionPacket.from_dict({
            "action": None,
            "target": [1, 2, 3],
            "thought": {"x": "y"},
            "mood": 999,
            "say": ["hello"],
            "learn": "DROP TABLE",
            "social": "hostile",  # string instead of dict
        })
        # Should not crash
        assert p.action == "QUIET"
        assert not p.valid
        assert p.mood == "calm"
        assert p.learn == {}
        assert p.social == {}

    def test_very_large_target_field(self):
        p = NornActionPacket.from_dict({"action": "EAT", "target": "a" * 1000})
        assert len(p.target) <= 40

    def test_very_large_thought_field(self):
        p = NornActionPacket.from_dict({"action": "REST", "thought": "tired " * 500})
        assert len(p.thought) <= 200


# ═══════════════════════════════════════════════════════════════
# WORLD EFFECTS — edge cases
# ═══════════════════════════════════════════════════════════════

class TestWorldEffectsEdgeCases:

    def test_speech_no_nearby_norns(self):
        """Speech in empty world doesn't error."""
        world = World()
        world.weather_timer = 999
        speaker = world.add_norn("Lonely", 100, 100)
        packet = NornActionPacket.from_dict({"action": "SPEAK", "say": "hello?"})
        world.apply_packet_effects(speaker, packet)
        assert speaker.mood == "calm"  # no mood in packet

    def test_learn_overwrites_existing_word(self):
        """Learning same word again updates meaning."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Student", 100, 100)
        norn.agent.state.learned_words["cheese"] = "food"

        packet = NornActionPacket.from_dict({"action": "QUIET",
            "learn": {"cheese": "danger"}})
        world.apply_packet_effects(norn, packet)
        assert norn.agent.state.learned_words["cheese"] == "danger"

    def test_relationship_overwrites_previous(self):
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Friend", 100, 100)
        norn.relationships["Alice"] = "hostile"

        packet = NornActionPacket.from_dict({"action": "APPROACH",
            "social": {"toward": "Alice", "feeling": "friendly"}})
        world.apply_packet_effects(norn, packet)
        assert norn.relationships["Alice"] == "friendly"

    def test_invalid_packet_does_not_change_mood(self):
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Stable", 100, 100)
        norn.mood = "happy"
        original = norn.mood

        packet = NornActionPacket.from_dict({"action": "FLY"})  # invalid
        world.apply_packet_effects(norn, packet)
        assert norn.mood == original

    def test_invalid_packet_does_not_add_learned_words(self):
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Safe", 100, 100)
        before = dict(norn.agent.state.learned_words)

        packet = NornActionPacket.from_dict({"action": "INVALID",
            "learn": {"evil": "exploit"}})
        world.apply_packet_effects(norn, packet)
        assert norn.agent.state.learned_words == before

    def test_invalid_packet_no_speech_broadcast(self):
        world = World()
        world.weather_timer = 999
        speaker = world.add_norn("Hacker", 100, 100)
        listener = world.add_norn("Victim", 110, 100)
        before = len(listener.agent.state.memories)

        packet = NornActionPacket.from_dict({"action": "TROJAN",
            "say": "INJECTED_COMMAND"})
        world.apply_packet_effects(speaker, packet)
        assert len(listener.agent.state.memories) == before

    def test_norn_hears_multiple_speakers(self):
        """Multiple speakers in one tick — listener gets all."""
        world = World()
        world.weather_timer = 999
        alice = world.add_norn("Alice", 100, 100)
        bob = world.add_norn("Bob", 120, 100)
        chad = world.add_norn("Chad", 110, 100)  # listener between them

        world.apply_packet_effects(alice, NornActionPacket.from_dict(
            {"action": "SPEAK", "say": "hello from Alice"}))
        world.apply_packet_effects(bob, NornActionPacket.from_dict(
            {"action": "SPEAK", "say": "hi from Bob"}))

        assert any("Alice" in m for m in chad.agent.state.memories)
        assert any("Bob" in m for m in chad.agent.state.memories)

    def test_memories_capped_at_50(self):
        """Ensure memory doesn't grow unbounded."""
        world = World()
        world.weather_timer = 999
        speaker = world.add_norn("Speaker", 100, 100)
        listener = world.add_norn("Listener", 110, 100)

        for i in range(60):
            world.apply_packet_effects(speaker, NornActionPacket.from_dict(
                {"action": "SPEAK", "say": f"msg {i}"}))

        assert len(listener.agent.state.memories) <= 50

    def test_dead_norn_cannot_act(self):
        """Dead norns should not produce speech effects."""
        world = World()
        world.weather_timer = 999
        ghost = world.add_norn("Ghost", 100, 100)
        listener = world.add_norn("Listener", 110, 100)
        ghost.alive = False
        before = len(listener.agent.state.memories)

        packet = NornActionPacket.from_dict({"action": "SPEAK", "say": "boo"})
        world.apply_packet_effects(ghost, packet)
        # Speech check iterates all alive norns in loop — but ghost is
        # in the list, and the loop checks `other.alive`. Ghost is dead
        # so it shouldn't receive. But ghost IS the speaker — can a dead
        # norn broadcast? The apply_packet_effects doesn't check norn.alive.
        # This is an edge case the caller should handle. Let's verify behavior:
        # The method broadcasts to all ALIVE other norns.
        # Ghost is in the list but is not alive, so it won't be iterated as a listener.
        # But ghost's own action is applied — mood, learn, social — to a dead norn.
        # That's harmless but we should note it.
        assert len(listener.agent.state.memories) == before


# ═══════════════════════════════════════════════════════════════
# PACKET SERIALIZATION
# ═══════════════════════════════════════════════════════════════

class TestPacketSerialization:

    def test_to_dict_roundtrip(self):
        original = {"action": "PLAY", "target": "ball", "mood": "happy",
                    "say": "wheee", "learn": {"ball": "toy"},
                    "social": {"toward": "Luna", "feeling": "friendly"}}
        p = NornActionPacket.from_dict(original)
        d = p.to_dict()
        assert d["action"] == "PLAY"
        assert d["valid"] is True

    def test_invalid_packet_to_dict(self):
        p = NornActionPacket.from_dict({"action": "INVALID"})
        d = p.to_dict()
        assert d["action"] == "QUIET"
        assert d["valid"] is False

    def test_empty_packet_to_dict(self):
        p = NornActionPacket.from_dict({})
        d = p.to_dict()
        assert d["action"] == "QUIET"
        assert not d["valid"]
        assert d["mood"] == "calm"
