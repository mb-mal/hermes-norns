"""
TDD tests for NornActionPacket — rich JSON protocol between LLM and game.
RED phase: all tests must FAIL.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
from action_packet import NornActionPacket, parse_llm_response


class TestPacketValidation:
    def test_valid_minimal_packet(self):
        p = NornActionPacket.from_dict({"action": "EAT"})
        assert p.action == "EAT"
        assert p.target == ""
        assert p.valid

    def test_invalid_action_falls_back_to_quiet(self):
        p = NornActionPacket.from_dict({"action": "FLY_TO_MOON"})
        assert p.action == "QUIET"
        assert not p.valid

    def test_lowercase_action_normalized(self):
        p = NornActionPacket.from_dict({"action": "eat", "target": "cheese"})
        assert p.action == "EAT"
        assert p.valid

    def test_mood_whitelisted(self):
        p = NornActionPacket.from_dict({"action": "PLAY", "mood": "happy"})
        assert p.mood == "happy"
        p2 = NornActionPacket.from_dict({"action": "PLAY", "mood": "transcendent"})
        assert p2.mood == "calm"

    def test_say_length_capped(self):
        p = NornActionPacket.from_dict({"action": "SPEAK", "say": "bla " * 100})
        assert len(p.say) <= 60

    def test_learn_max_3_entries(self):
        p = NornActionPacket.from_dict({"action": "QUIET", "learn": {f"w{i}": "food" for i in range(10)}})
        assert len(p.learn) <= 3

    def test_learn_values_sanitized(self):
        p = NornActionPacket.from_dict({"action": "QUIET", "learn": {"cheese": "x" * 500}})
        for v in p.learn.values():
            assert len(v) <= 30

    def test_social_feeling_whitelist(self):
        p = NornActionPacket.from_dict({"action": "APPROACH", "target": "Alice",
            "social": {"toward": "Alice", "feeling": "friendly"}})
        assert p.social["feeling"] == "friendly"
        p2 = NornActionPacket.from_dict({"action": "APPROACH", "social":
            {"toward": "Alice", "feeling": "quantum_entangled"}})
        assert p2.social["feeling"] == "neutral"

    def test_unknown_fields_dropped(self):
        p = NornActionPacket.from_dict({"action": "EAT", "target": "cheese",
            "hunger": 0.0, "teleport_to": [0,0], "fitness": 9999})
        assert not hasattr(p, "hunger")

    def test_thought_kept(self):
        p = NornActionPacket.from_dict({"action": "REST", "thought": "so sleepy"})
        assert p.thought == "so sleepy"

    def test_none_gives_invalid(self):
        p = NornActionPacket.from_dict(None)
        assert p.action == "QUIET"
        assert not p.valid


class TestParserRobustness:
    def test_plain_json(self):
        p = parse_llm_response('{"action": "EAT", "target": "cheese", "thought": "yum"}')
        assert p.action == "EAT"

    def test_json_in_code_fence(self):
        p = parse_llm_response('Decision:\n```json\n{"action": "REST", "thought": "tired"}\n```')
        assert p.action == "REST"

    def test_json_with_surrounding_text(self):
        p = parse_llm_response('The norn is hungry. {"action": "EAT", "target": "apple"} That is it.')
        assert p.action == "EAT"

    def test_multiple_json_takes_first_with_action(self):
        p = parse_llm_response('{"note": "x"} {"action": "PLAY", "target": "ball"}')
        assert p.action == "PLAY"

    def test_garbage_returns_invalid(self):
        p = parse_llm_response("I refuse to answer in JSON!")
        assert p.action == "QUIET"
        assert not p.valid

    def test_empty_string(self):
        p = parse_llm_response("")
        assert p.action == "QUIET"

    def test_truncated_json_safe(self):
        p = parse_llm_response('{"action": "EAT", "target": "chee')
        assert p.action == "QUIET"
        assert not p.valid

    def test_single_quotes_accepted(self):
        p = parse_llm_response("{'action': 'REST', 'thought': 'sleepy'}")
        assert p.action == "REST"

    def test_trailing_comma(self):
        p = parse_llm_response('{"action": "PLAY", "target": "ball",}')
        assert p.action == "PLAY"
