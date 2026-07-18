"""
Hermes Norns — Genetics & Evolution System
Mendelian allele pairs, mutations, phenotype expression, speciation.
"""
import random
from dataclasses import dataclass, field
from typing import Optional

# ── Allele System ────────────────────────────────────────────────

TRAIT_NAMES = [
    "curiosity", "aggression", "sociability", "playfulness",
    "cautiousness", "intelligence",
    "size", "speed", "metabolism",
    "red_pigment", "green_pigment", "blue_pigment",
    "diet_herbivory", "diet_carnivory",
    "lifespan_factor", "fertility",
]

@dataclass
class AllelePair:
    """A gene with dominant and recessive alleles."""
    dominant: float
    recessive: float
    name: str = ""

    @property
    def expressed(self) -> float:
        """Dominant allele determines phenotype."""
        return self.dominant

    def mutate(self, delta: float, target: str = "random"):
        """Apply a mutation delta. target can be 'dominant', 'recessive', or 'random'."""
        allele = target if target in ("dominant", "recessive") else random.choice(["dominant", "recessive"])
        if allele == "dominant":
            self.dominant = max(0.01, min(1.0, self.dominant + delta))
        else:
            self.recessive = max(0.01, min(1.0, self.recessive + delta))

    def copy(self) -> "AllelePair":
        return AllelePair(dominant=self.dominant, recessive=self.recessive, name=self.name)


@dataclass
class NornGenome:
    """Complete genome with allele pairs for all traits."""
    alleles: dict = field(default_factory=dict)
    mutation_rate: float = 0.02
    generation: int = 0
    species_id: str = ""

    def __post_init__(self):
        if not self.alleles:
            self.alleles = {}
            for trait in TRAIT_NAMES:
                v = random.uniform(0.3, 0.7)
                self.alleles[trait] = AllelePair(
                    dominant=v,
                    recessive=random.uniform(0.1, 0.9),
                    name=trait,
                )

    def set_alleles(self, trait: str, dominant: float, recessive: float):
        """Set both alleles for a trait."""
        self.alleles[trait] = AllelePair(dominant=dominant, recessive=recessive, name=trait)

    @property
    def curiosity(self) -> float:
        return self.alleles.get("curiosity", AllelePair(0, 0)).expressed

    @property
    def aggression(self) -> float:
        return self.alleles.get("aggression", AllelePair(0, 0)).expressed

    @property
    def sociability(self) -> float:
        return self.alleles.get("sociability", AllelePair(0, 0)).expressed

    @property
    def playfulness(self) -> float:
        return self.alleles.get("playfulness", AllelePair(0, 0)).expressed

    @property
    def cautiousness(self) -> float:
        return self.alleles.get("cautiousness", AllelePair(0, 0)).expressed

    @property
    def intelligence(self) -> float:
        return self.alleles.get("intelligence", AllelePair(0, 0)).expressed

    @property
    def size(self) -> float:
        return self.alleles.get("size", AllelePair(0, 0)).expressed

    @property
    def speed(self) -> float:
        return self.alleles.get("speed", AllelePair(0, 0)).expressed

    @property
    def metabolism(self) -> float:
        return self.alleles.get("metabolism", AllelePair(0, 0)).expressed

    def __getattr__(self, name):
        """Fallback for trait access. Guarded against pickle recursion."""
        if name.startswith("_") or name == "alleles":
            raise AttributeError(name)
        # alleles may not be set during unpickling
        if "_alleles" not in self.__dict__ and "alleles" not in self.__dict__:
            raise AttributeError(name)
        if name in getattr(self, "alleles", {}):
            return self.alleles[name].expressed
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def breed_with(self, other: "NornGenome", child_name: str) -> "NornGenome":
        """Mendelian breeding: one random allele from each parent per trait."""
        child = NornGenome()
        child.generation = max(self.generation, other.generation) + 1
        child.species_id = self.species_id or other.species_id

        for trait in TRAIT_NAMES:
            mom_pair = self.alleles.get(trait, AllelePair(0.5, 0.5))
            dad_pair = other.alleles.get(trait, AllelePair(0.5, 0.5))

            # Random: which allele from each parent
            from_mom = random.choice([mom_pair.dominant, mom_pair.recessive])
            from_dad = random.choice([dad_pair.dominant, dad_pair.recessive])

            # Dominant is the higher value
            if from_mom >= from_dad:
                child.alleles[trait] = AllelePair(
                    dominant=from_mom, recessive=from_dad, name=trait
                )
            else:
                child.alleles[trait] = AllelePair(
                    dominant=from_dad, recessive=from_mom, name=trait
                )

        # Apply mutations
        avg_mutation_rate = (self.mutation_rate + other.mutation_rate) / 2
        for trait in TRAIT_NAMES:
            if random.random() < avg_mutation_rate:
                delta = random.uniform(-0.25, 0.25)
                child.alleles[trait].mutate(delta)

        return child

    def force_mutation(self, trait: str, delta: float, target: str = "dominant"):
        """Artificially trigger a mutation. Default targets dominant allele for visibility."""
        if trait in self.alleles:
            self.alleles[trait].mutate(delta, target)

    def get_phenotype(self) -> dict:
        """Return all expressed traits (phenotype)."""
        return {trait: pair.expressed for trait, pair in self.alleles.items()}

    def to_legacy_dna(self):
        """Convert to legacy NornDNA for backward compat."""
        from norn_agent import NornDNA
        return NornDNA(
            name="",
            curiosity=self.curiosity,
            aggression=self.aggression,
            sociability=self.sociability,
            playfulness=self.playfulness,
            cautiousness=self.cautiousness,
            intelligence=self.intelligence,
        )
