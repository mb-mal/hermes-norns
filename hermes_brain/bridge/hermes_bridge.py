"""
Hermes Norns — C++ Bridge to openc2e Engine
============================================
Design document + Python-side implementation of the IPC bridge.

Architecture:
  openc2e Creature::tick()
         │
    c2eBrain::tick()     ← perceives world (lobes: perception, drive, concept)
         │                   
    ┌────▼────────────┐
    │  hermes-bridge   │  ← NEW: replaces decision lobe
    │  (subprocess)    │     
    │  stdin/stdout    │  ← JSON protocol
    │  JSON protocol   │     
    └────┬────────────┘
         │
    norn_agent.py      ← our already-working LLM brain
         │
    action_packet.py    ← validated action
         │
    ┌────▼────────────┐
    │  Decision Lobe   │  ← openc2e applies: move, eat, play...
    └─────────────────┘

IPC Protocol (on stdin/stdout):
  → {"type":"perception","tick":N,"drives":{...},"visible":[...]}
  ← {"type":"action","action":"EAT","target":"cheese",...}

Two modes:
  1. REPLACE (default): LLM fully replaces decision lobe
  2. HYBRID: LLM gives high-level goal, local brain handles motor execution

Status: DESIGN phase. Bridge code below implements Python side.
"""

import json
import sys
import threading
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

# Add hermes_brain/python to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hermes_brain" / "python"))

# ── Protocol ──────────────────────────────────────────────────────

@dataclass
class BridgePerception:
    """Perception packet: openc2e → Python bridge."""
    type: str = "perception"
    tick: int = 0
    creature_id: str = ""
    drives: dict = None
    visible_objects: list = None  # [{name, type, x, y, distance}]
    biochemistry: dict = None
    genome_snapshot: dict = None  # key gene values
    # openc2e-specific
    lobe_activations: dict = None  # neuron activations from key lobes

    def __post_init__(self):
        if self.drives is None:
            self.drives = {}
        if self.visible_objects is None:
            self.visible_objects = []
        if self.biochemistry is None:
            self.biochemistry = {}
        if self.genome_snapshot is None:
            self.genome_snapshot = {}
        if self.lobe_activations is None:
            self.lobe_activations = {}


@dataclass
class BridgeAction:
    """Action packet: Python bridge → openc2e."""
    type: str = "action"
    creature_id: str = ""
    action: str = "QUIET"          # EAT, APPROACH, TRAVEL, etc.
    target: str = ""               # object name or direction
    thought: str = ""              # LLM reasoning
    mood: str = "calm"
    intensity: float = 0.5         # 0-1: how vigorously to act
    
    # Advanced: direct lobe injection (HYBRID mode)
    decision_activation: Optional[float] = None  # inject into decision lobe neuron
    verb_activation: Optional[str] = None        # inject verb lobe
    noun_activation: Optional[str] = None        # inject noun lobe


# ── Bridge Server ──────────────────────────────────────────────────

class HermesBridge:
    """
    Python-side bridge server.
    
    Usage:
        bridge = HermesBridge(stdin=sys.stdin, stdout=sys.stdout)
        bridge.serve()  # blocking loop
    
    Or from openc2e C++ side, spawn as subprocess:
        bridge = subprocess(['python3', 'hermes_bridge.py'])
        bridge.stdin.write(perception_json + '\n')
        action_json = bridge.stdout.readline()
    """

    def __init__(self, stdin=None, stdout=None, model="deepseek-v4-pro"):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.model = model
        self._agent = None  # lazy init
        self._running = False

    def serve(self):
        """Main loop: read perception → decide → write action."""
        self._running = True
        while self._running:
            line = self.stdin.readline()
            if not line:
                break  # EOF — parent closed pipe
            
            try:
                perception = BridgePerception(**json.loads(line.strip()))
            except Exception:
                # Malformed input — respond with quiet
                resp = BridgeAction().to_response_json()
                self.stdout.write(resp + "\n")
                self.stdout.flush()
                continue

            action = self._decide(perception)
            self.stdout.write(action.to_response_json() + "\n")
            self.stdout.flush()

    def _decide(self, per: BridgePerception) -> BridgeAction:
        """Call LLM to decide action from perception."""
        try:
            from norn_agent import NornAgent, NornDNA
            from perception_v2 import format_perception_v2
            from action_packet import parse_llm_response
            import subprocess

            # Build perception for our prompt
            p = {
                "tick": per.tick,
                "dna_traits": {
                    "name": per.creature_id,
                    "curiosity": per.genome_snapshot.get("curiosity", 0.5),
                    "sociability": per.genome_snapshot.get("sociability", 0.5),
                    "playfulness": per.genome_snapshot.get("playfulness", 0.5),
                    "aggression": per.genome_snapshot.get("aggression", 0.3),
                    "cautiousness": per.genome_snapshot.get("cautiousness", 0.4),
                    "intelligence": per.genome_snapshot.get("intelligence", 0.5),
                },
                "drives": per.drives,
                "biochemistry": per.biochemistry,
                "visible_objects": per.visible_objects,
                "nearby_norns": per.lobe_activations.get("nearby_norns", []),
                "learned_words": {},
                "recent_memories": [],
                "weather": "cloudy",  # openc2e can pass this
            }

            prompt = format_perception_v2(p)
            result = subprocess.run(
                ["hermes", "-z", prompt, "-m", self.model],
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode == 0:
                packet = parse_llm_response(result.stdout.strip())
                if packet.valid:
                    return BridgeAction(
                        creature_id=per.creature_id,
                        action=packet.action,
                        target=packet.target,
                        thought=packet.thought,
                        mood=packet.mood,
                    )
        except Exception:
            pass

        return BridgeAction(creature_id=per.creature_id, action="QUIET")

    def to_response_json(self) -> str:
        """Serialise action to JSON line for openc2e."""
        return json.dumps({
            "type": "action",
            "creature_id": self.creature_id,
            "action": self.action,
            "target": self.target,
            "thought": self.thought,
            "mood": self.mood,
            "intensity": self.intensity,
        })


# ── C++ Integration Guide ─────────────────────────────────────────

INTEGRATION_GUIDE = """
=== INTEGRATING HERMES BRIDGE INTO OPENC2E ===

1. Add to CMakeLists.txt:
   find_package(Python3 COMPONENTS Interpreter)
   target_link_libraries(openc2e PRIVATE Python3::Python)

2. In Creature::tick() or c2eBrain::tick(), after perception lobe fires:
   
   // 1) Collect perception from lobes
   json per = {
     {"type", "perception"},
     {"tick", world.tickcount},
     {"creature_id", getCreatureId()},
     {"drives", getDriveLevels()},      // from drive lobe
     {"visible_objects", getVisible()}, // from perception lobe
     {"biochemistry", getChemLevels()}, // from biochemistry
     {"genome_snapshot", getKeyGenes()},
   };

   // 2) Send to bridge
   if (bridgesubprocess) {
     bridgesubprocess.stdin << per.dump() << std::endl;
     
     // 3) Read response
     std::string response;
     std::getline(bridgesubprocess.stdout, response);
     json action = json::parse(response);
     
     // 4) Apply to decision lobe
     if (action["action"] == "EAT") {
       decisionLobe->inject("push");     // trigger PUSH toward food
       decisionLobe->inject("eat");      // trigger EAT when close
     } else if (action["action"] == "TRAVEL") {
       direction = action["target"];
       decisionLobe->inject("move_" + direction);
     }
     // ... etc for each action type
   } else {
     // Fallback: use original brain
     decisionLobe->tick();
   }

3. Build:
   mkdir build && cd build
   cmake .. -DPYTHON_BRIDGE=ON
   make -j$(nproc)
"""


if __name__ == "__main__":
    print("Hermes Bridge — Python side of openc2e integration")
    print(INTEGRATION_GUIDE)
    
    # If run directly, start bridge server
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        bridge = HermesBridge()
        bridge.serve()
