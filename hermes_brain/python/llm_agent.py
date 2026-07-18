#!/usr/bin/env python3
"""
Hermes Norn — LLM-backed agent (V2).
Uses Hermes Agent CLI with rich perception context.
Falls back: llama-cpp → MLX → rule-based.
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from norn_agent import NornAgent, NornDNA, rule_based_action
from perception_v2 import format_perception_v2
from action_packet import NornActionPacket, parse_llm_response


class LLMNornAgent(NornAgent):
    """Norn agent with LLM brain — uses Hermes Agent CLI for reasoning."""

    def __init__(self, model: str = "deepseek-v4-pro", use_llm: bool = True):
        super().__init__(use_llm=use_llm)
        self.model = model
        self._last_raw_response = ""
        self.last_packet = None

    def _llm_decision(self, perception: dict) -> dict:
        """Try LLM backends: Hermes CLI → llama-cpp → MLX → rules."""
        if self.state.dna:
            perception["dna_traits"] = {
                "name": self.state.dna.name,
                "curiosity": self.state.dna.curiosity,
                "sociability": self.state.dna.sociability,
                "playfulness": self.state.dna.playfulness,
                "aggression": self.state.dna.aggression,
                "cautiousness": self.state.dna.cautiousness,
                "intelligence": self.state.dna.intelligence,
            }

        # 1. Hermes Agent CLI → validated packet
        result = self._try_hermes_cli(perception)
        if result:
            return result
        # 2. llama-cpp
        result = self._try_llama_cpp(perception)
        if result:
            return result
        # 3. MLX
        result = self._try_mlx(perception)
        if result:
            return result
        # 4. Fallback
        return rule_based_action(perception)

    def _try_hermes_cli(self, perception: dict) -> Optional[dict]:
        """Call Hermes Agent CLI. Returns validated packet as dict."""
        try:
            prompt = format_perception_v2(perception)
            result = subprocess.run(
                ["hermes", "-z", prompt, "-m", self.model],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return None
            response = result.stdout.strip()
            self._last_raw_response = response
            packet = parse_llm_response(response)
            self.last_packet = packet
            if not packet.valid:
                return None
            return packet.to_dict()
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return None

    def _try_llama_cpp(self, perception: dict) -> Optional[dict]:
        """Try llama-cpp-python with local GGUF model."""
        try:
            from llama_cpp import Llama
            candidates = [
                Path.home() / "models" / "llama-3.2-3b-instruct-q4_k_m.gguf",
                Path.home() / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf",
                Path.home() / ".cache/lm-studio/models" / "hermes-norn.gguf",
            ]
            model_path = None
            for mp in candidates:
                if mp.exists():
                    model_path = mp
                    break
            if not model_path:
                return None
            if not hasattr(self, "_llama_model"):
                self._llama_model = Llama(
                    model_path=str(model_path), n_ctx=2048, n_threads=4, verbose=False)
            prompt = format_perception_v2(perception)
            system = "You are a Norn creature. Respond with JSON only."
            full_prompt = f"<|system|>\n{system}\n<|user|>\n{prompt}\n<|assistant|>"
            output = self._llama_model(
                full_prompt, max_tokens=150, temperature=0.7,
                stop=["<|user|>", "<|system|>"],
            )
            return self._parse_json(output["choices"][0]["text"].strip())
        except ImportError:
            return None

    def _try_mlx(self, perception: dict) -> Optional[dict]:
        """Try MLX on Apple Silicon."""
        try:
            from mlx_lm import load, generate
            if not hasattr(self, "_mlx_model"):
                model_name = "mlx-community/Llama-3.2-3B-Instruct-4bit"
                self._mlx_model, self._mlx_tokenizer = load(model_name)
            prompt = format_perception_v2(perception)
            messages = [
                {"role": "system", "content": "You are a Norn creature. JSON only."},
                {"role": "user", "content": prompt},
            ]
            full_prompt = self._mlx_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            response = generate(
                self._mlx_model, self._mlx_tokenizer,
                prompt=full_prompt, max_tokens=150, temp=0.7,
            )
            return self._parse_json(response)
        except ImportError:
            return None

    @staticmethod
    def _parse_json(text: str) -> Optional[dict]:
        """Extract JSON from LLM response (legacy fallback)."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{\s*"action"\s*:\s*"[^"]*".*?\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
