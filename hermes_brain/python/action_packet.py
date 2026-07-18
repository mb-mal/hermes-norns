"""
NornActionPacket — structured JSON protocol between LLM brain and game engine.

Protocol design:
  LLM proposes → Validator sanitizes → World applies (safe side-effects only)

The LLM writes:
  - action, target, thought  (base action)
  - mood                     (emotional coloring)
  - say                      (utterance for SPEAK action)
  - learn                    (words learned this tick)
  - social                   (relationship signal toward another Norn)

The validator:
  - Whitelists: actions, moods, social feelings
  - Caps: say length, learn entries, word meaning length
  - Drops: unknown fields (prevents cheating)
  - Falls back: invalid action → QUIET
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional


# ── Whitelists ────────────────────────────────────────────────────

VALID_ACTIONS = {
    "APPROACH", "EAT", "PUSH", "PICKUP", "DROP",
    "SPEAK", "REST", "PLAY", "TRAVEL", "BREED", "QUIET",
}

VALID_MOODS = {
    "happy", "sad", "excited", "scared", "angry",
    "curious", "content", "playful", "tired", "calm",
    "loving", "lonely", "nervous", "proud", "confused",
}

VALID_SOCIAL_FEELINGS = {
    "friendly", "neutral", "hostile", "loving",
    "curious", "scared", "playful", "protective",
}

# ── Packet ────────────────────────────────────────────────────────

@dataclass
class NornActionPacket:
    """Safe, validated action packet from LLM to game engine."""

    action: str = "QUIET"
    target: str = ""
    thought: str = ""
    mood: str = "calm"
    say: str = ""
    learn: dict = field(default_factory=dict)
    social: dict = field(default_factory=dict)
    valid: bool = True  # False if the packet was coerced/corrected

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "NornActionPacket":
        """Parse + validate a dict into a safe packet."""
        if not isinstance(data, dict):
            return cls(action="QUIET", valid=False)

        # ── Action (required, whitelisted) ──
        raw_action = str(data.get("action", "")).strip().upper()
        if raw_action not in VALID_ACTIONS:
            raw_action = "QUIET"
            valid = False
        else:
            valid = True

        # ── Target (any string, capped) ──
        target = str(data.get("target", ""))[:40]

        # ── Thought (free text, capped) ──
        thought = str(data.get("thought", ""))[:200]

        # ── Mood (whitelisted) ──
        mood = str(data.get("mood", "calm")).lower().strip()
        if mood not in VALID_MOODS:
            mood = "calm"

        # ── Say (utterance for SPEAK, capped) ──
        say = str(data.get("say", ""))[:60]

        # ── Learn (max 3 word-meaning pairs, sanitized) ──
        learn = {}
        raw_learn = data.get("learn", {})
        if isinstance(raw_learn, dict):
            count = 0
            for word, meaning in list(raw_learn.items())[:3]:
                word = str(word)[:30]
                meaning = str(meaning)[:30]
                if word and meaning:
                    learn[word] = meaning
                    count += 1

        # ── Social (whitelisted feeling toward someone) ──
        social = {}
        raw_social = data.get("social", {})
        if isinstance(raw_social, dict):
            toward = str(raw_social.get("toward", ""))[:40]
            feeling = str(raw_social.get("feeling", "neutral")).lower()
            if feeling not in VALID_SOCIAL_FEELINGS:
                feeling = "neutral"
            if toward:
                social = {"toward": toward, "feeling": feeling}

        return cls(
            action=raw_action,
            target=target,
            thought=thought,
            mood=mood,
            say=say,
            learn=learn,
            social=social,
            valid=valid,
        )

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "thought": self.thought,
            "mood": self.mood,
            "say": self.say,
            "learn": self.learn,
            "social": self.social,
            "valid": self.valid,
        }


# ── Parser — handles any LLM output format ────────────────────────

def parse_llm_response(text: str) -> NornActionPacket:
    """
    Extract an action packet from LLM output.
    Handles: plain JSON, code-fenced JSON, JSON-in-prose, Python dicts,
             truncated JSON, multiple JSON objects, and garbage.
    Returns a valid (possibly coerced) NornActionPacket. Never crashes.
    """
    if not text or not text.strip():
        return NornActionPacket(action="QUIET", valid=False)

    candidates = []

    # 1. ```json ... ``` code blocks
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        candidates.append(match.group(1))

    # 2. Balanced-brace JSON objects containing "action"
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    if '"action"' in candidate or "'action'" in candidate:
                        candidates.append(candidate)
                    break

    # 3. Single-quote Python dicts (fallback)
    for match in re.finditer(r"\{(?:[^{}]|'[^']*')*?'action'(?:[^{}]|'[^']*')*?\}", text, re.DOTALL):
        if match.group() not in candidates:
            candidates.append(match.group())

    # Try each candidate
    for cand in candidates:
        # Handle trailing commas
        cand_clean = re.sub(r",\s*}", "}", cand)
        cand_clean = re.sub(r",\s*\]", "]", cand_clean)

        try:
            data = json.loads(cand_clean)
        except json.JSONDecodeError:
            # Try converting single quotes to double
            try:
                data = json.loads(cand_clean.replace("'", '"'))
            except json.JSONDecodeError:
                continue

        if isinstance(data, dict) and "action" in data:
            packet = NornActionPacket.from_dict(data)
            if packet.valid:
                return packet

    # 4. Garbage — return invalid QUIET
    return NornActionPacket(action="QUIET", valid=False)
