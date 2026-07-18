#!/usr/bin/env python3
"""
Hermes Norn — LLM-backed agent.
Uses Hermes Agent CLI for reasoning when available, falls back to llama-cpp.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from norn_agent import NornAgent, NornDNA, format_perception, rule_based_action


ACTIONS_JSON = """Valid actions (respond ONLY with a JSON object):
{
  "action": "EAT|APPROACH|PUSH|PICKUP|DROP|REST|PLAY|TRAVEL|BREED|SPEAK|QUIET",
  "target": "object name or direction",
  "thought": "your reasoning"
}"""


class LLMNornAgent(NornAgent):
    """Norn agent that uses an LLM for decision-making."""

    def __init__(self, model: str = "auto", use_llm: bool = True):
        super().__init__(use_llm=use_llm)
        self.model = model

    def _llm_decision(self, perception: dict) -> dict:
        """Try multiple LLM backends in order of preference."""

        perception["dna_traits"] = self.state.dna.__dict__
        prompt = format_perception(perception)

        # 1. Hermes Agent CLI
        result = self._try_hermes_cli(prompt)
        if result:
            return result

        # 2. llama-cpp-python (local GGUF)
        result = self._try_llama_cpp(prompt)
        if result:
            return result

        # 3. mlx-lm (Apple Silicon)
        result = self._try_mlx(prompt)
        if result:
            return result

        # 4. Fallback: rule-based
        return rule_based_action(perception)

    def _try_hermes_cli(self, prompt: str) -> Optional[dict]:
        """Try Hermes Agent CLI."""
        try:
            # Prepare a compact system prompt + user message
            system = """You are a Norn — a small alien creature in the game Creatures.
You decide what to do based on your drives, personality, and what you see.
Respond ONLY with a JSON action. No explanation, no markdown, just the JSON."""

            full_prompt = f"{system}\n\n{prompt}\n\n{ACTIONS_JSON}"

            result = subprocess.run(
                ["hermes", "agent", "--prompt", full_prompt, "--model", self.model],
                capture_output=True, text=True, timeout=15,
                env={**__import__('os').environ, "HERMES_JSON_MODE": "1"}
            )
            if result.returncode == 0:
                response = result.stdout.strip()
                # Try to extract JSON from response
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # Maybe there's JSON embedded in text
                    import re
                    match = re.search(r'\{[^{}]*"action"[^{}]*\}', response)
                    if match:
                        return json.loads(match.group())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _try_llama_cpp(self, prompt: str) -> Optional[dict]:
        """Try llama-cpp-python."""
        try:
            from llama_cpp import Llama

            model_path = Path.home() / ".cache/lm-studio/models" / "hermes-norn.gguf"
            # Try common model locations
            candidates = [
                model_path,
                Path.home() / "models" / "llama-3.2-3b-instruct-q4_k_m.gguf",
                Path.home() / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf",
            ]
            for mp in candidates:
                if mp.exists():
                    model_path = mp
                    break
            else:
                return None

            if not hasattr(self, '_llama_model'):
                self._llama_model = Llama(
                    model_path=str(model_path),
                    n_ctx=2048,
                    n_threads=4,
                    verbose=False,
                )

            system = "You are a Norn creature. Respond with JSON only: {\"action\": \"...\", \"target\": \"...\", \"thought\": \"...\"}"
            full_prompt = f"<|system|>\n{system}\n<|user|>\n{prompt}\n<|assistant|>"

            output = self._llama_model(
                full_prompt,
                max_tokens=150,
                temperature=0.7,
                stop=["<|user|>", "<|system|>"],
            )

            response = output["choices"][0]["text"].strip()
            import re
            match = re.search(r'\{[^{}]*"action"[^{}]*\}', response)
            if match:
                return json.loads(match.group())

        except ImportError:
            pass
        return None

    def _try_mlx(self, prompt: str) -> Optional[dict]:
        """Try MLX on Apple Silicon."""
        try:
            import mlx.core as mx
            from mlx_lm import load, generate

            if not hasattr(self, '_mlx_model'):
                model_name = "mlx-community/Llama-3.2-3B-Instruct-4bit"
                self._mlx_model, self._mlx_tokenizer = load(model_name)

            system = "You are a Norn creature. Respond with JSON only."
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
            full_prompt = self._mlx_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            response = generate(
                self._mlx_model, self._mlx_tokenizer,
                prompt=full_prompt, max_tokens=150, temp=0.7
            )

            import re
            match = re.search(r'\{[^{}]*"action"[^{}]*\}', response)
            if match:
                return json.loads(match.group())

        except ImportError:
            pass
        return None


# ── Test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🧠 LLM Norn Agent test\n")

    agent = LLMNornAgent(use_llm=True)
    agent.state.dna = NornDNA(
        name="TestNorn",
        curiosity=0.8, sociability=0.7, playfulness=0.6,
        aggression=0.2, cautiousness=0.3, intelligence=0.7
    )

    perception = {
        "tick": 42,
        "drives": {"hunger": 0.85, "thirst": 0.3, "fatigue": 0.2, "boredom": 0.4,
                    "loneliness": 0.5, "fear": 0.1, "pain": 0.0, "anger": 0.1,
                    "sex_drive": 0.1, "crowded": 0.1},
        "visible_objects": [
            {"type": "food", "name": "cheese", "distance": 50, "direction": "left"},
            {"type": "toy", "name": "ball", "distance": 200, "direction": "right"},
            {"type": "norn", "name": "Alice", "distance": 150, "direction": "front"},
        ],
        "learned_words": {"cheese": "food", "ball": "toy"},
        "recent_memories": ["ate apple 30 ticks ago — tasty"],
        "life_stage": "adolescent",
    }

    action = agent.perceive(perception)
    print(json.dumps(action, indent=2, ensure_ascii=False))
