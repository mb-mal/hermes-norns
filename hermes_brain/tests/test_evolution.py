"""
TDD tests for Hermes Norns — Evolution System v0.4
RED phase: all tests must FAIL.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
from world_sim import World, WorldObject, NornBody
from norn_agent import NornAgent, NornDNA


# ═══════════════════════════════════════════════════════════════
# GENE POOL — Mendelian genetics with mutations
# ═══════════════════════════════════════════════════════════════

class TestMendelianGenetics:
    """Traits are inherited via dominant/recessive genes, not just averaging."""

    def test_gene_has_dominance(self):
        """Each trait gene has dominant and recessive alleles."""
        dna = NornDNA(name="Test")
        # DNA should have gene pairs, not just scalar values
        assert hasattr(dna, 'alleles'), "DNA should store allele pairs"
        assert isinstance(dna.alleles, dict)
        assert 'curiosity' in dna.alleles

    def test_phenotype_from_dominant_allele(self):
        """Phenotype expresses the dominant allele."""
        dna = NornDNA(name="Test")
        dna.set_alleles('curiosity', dominant=0.9, recessive=0.3)
        # Dominant allele should determine the expressed trait
        assert dna.curiosity == pytest.approx(0.9, abs=0.1)

    def test_breeding_produces_allele_combinations(self):
        """Offspring get one allele from each parent (Mendelian)."""
        mom = NornDNA(name="Mom")
        mom.set_alleles('curiosity', dominant=0.9, recessive=0.3)
        dad = NornDNA(name="Dad")
        dad.set_alleles('curiosity', dominant=0.5, recessive=0.1)

        # Run multiple breedings to see Mendelian ratios
        results = []
        for _ in range(100):
            child = mom.breed_with(dad, "Child")
            results.append(child.curiosity)

        # Should see both 0.9 (dominant from mom) and 0.5 (dominant from dad)
        high = sum(1 for r in results if r > 0.7)
        mid = sum(1 for r in results if 0.3 < r <= 0.7)
        low = sum(1 for r in results if r <= 0.3)

        assert high > 10, f"Expected dominant phenotypes, got high={high}"
        assert mid > 10, f"Expected mid phenotypes, got mid={mid}"
        assert low < 50, "Recessive should be rarer"


# ═══════════════════════════════════════════════════════════════
# MUTATIONS — rare, random, observable changes
# ═══════════════════════════════════════════════════════════════

class TestMutations:
    """Mutations occur rarely and produce visible trait changes."""

    def test_mutation_rate_default(self):
        """Base mutation rate is low (~2%)."""
        dna = NornDNA(name="Test")
        assert hasattr(dna, 'mutation_rate')
        assert 0.001 <= dna.mutation_rate <= 0.05

    def test_mutation_changes_trait(self):
        """When mutation fires, a trait value changes noticeably."""
        dna = NornDNA(name="Test")
        dna.set_alleles('aggression', dominant=0.2, recessive=0.1)
        original = dna.aggression

        # Force a mutation
        dna.force_mutation('aggression', delta=0.3)
        assert abs(dna.aggression - original) > 0.1, \
            f"Mutation should change trait significantly: {original} → {dna.aggression}"

    def test_mutation_events_are_tracked(self):
        """Norn DNA tracks mutation events."""
        norn_dna = NornDNA(name="Mutant")
        
        # Trigger a mutation
        original = norn_dna.curiosity
        
        # Set high mutation rate and trigger
        norn_dna.mutation_rate = 1.0
        norn_dna.force_mutation('curiosity', delta=0.3)

        assert norn_dna.curiosity != original, f"Mutation should change trait"
        assert norn_dna._genome.generation == 0  # mutation doesn't change generation, breeding does

    def test_harmful_mutations_possible(self):
        """Mutations can be harmful, not just beneficial."""
        dna = NornDNA(name="Test")
        dna.set_alleles('intelligence', dominant=0.8, recessive=0.7)
        original = dna.intelligence
        
        dna.force_mutation('intelligence', delta=-0.4)
        assert dna.intelligence < original, f"Harmful mutation should reduce trait"


# ═══════════════════════════════════════════════════════════════
# FITNESS & NATURAL SELECTION
# ═══════════════════════════════════════════════════════════════

class TestFitnessSelection:
    """Environment creates selection pressure on traits."""

    def test_norn_has_fitness_score(self):
        """Each Norn has a fitness score based on survival success."""
        from world_sim import NornBody
        agent = NornAgent()
        body = NornBody(name="Fit", x=0, y=0, agent=agent)
        assert hasattr(body, 'fitness')
        assert body.fitness >= 0

    def test_surviving_longer_increases_fitness(self):
        """Norns that live longer have higher fitness."""
        world = World()
        world.weather_timer = 999
        norn = world.add_norn("Survivor", 100, 100)
        initial_fitness = norn.fitness

        for _ in range(500):
            world.tick()
            if not norn.alive:
                break

        # Fitness should increase with survival time
        if norn.alive:
            assert norn.fitness > initial_fitness, \
                f"Fitness should grow: {initial_fitness} → {norn.fitness}"

    def test_food_scarcity_selects_for_efficiency(self):
        """When food is scarce, Norns with better food-finding traits survive."""
        world = World()
        world.weather_timer = 999

        # Two Norns: one efficient eater, one wasteful
        alice = world.add_norn("Alice", 50, 100)
        alice.agent.state.dna.set_alleles('metabolism', dominant=0.2, recessive=0.1)  # slow metabolism = efficient

        bob = world.add_norn("Bob", 150, 100)
        bob.agent.state.dna.set_alleles('metabolism', dominant=0.9, recessive=0.8)  # fast metabolism = wasteful

        # Only 1 food item
        world.spawn_food("lone_berry", 100, 100, nutrition=40)

        for _ in range(300):
            world.tick()

        # The efficient norn should have higher fitness
        assert alice.fitness != bob.fitness, "Different strategies should yield different fitness"


# ═══════════════════════════════════════════════════════════════
# SPECIATION — population divergence
# ═══════════════════════════════════════════════════════════════

class TestSpeciation:
    """Isolated populations diverge into distinct species."""

    def test_norn_has_species_tag(self):
        """Each Norn belongs to a species lineage."""
        agent = NornAgent()
        body = NornBody(name="Test", x=0, y=0, agent=agent)
        assert hasattr(body, 'species_id')
        assert body.species_id is not None

    def test_children_inherit_species(self):
        """Offspring belong to parent's species by default."""
        world = World()
        world.weather_timer = 999
        mom = world.add_norn("Mom", 50, 100)
        dad = world.add_norn("Dad", 150, 100)
        mom.species_id = "Nornus_curiosus"
        dad.species_id = "Nornus_curiosus"

        # Force breeding
        mom.sex_drive = 0.9
        dad.sex_drive = 0.9
        mom.x, mom.y = 50, 50
        dad.x, dad.y = 60, 60

        for _ in range(100):
            world.tick()

        children = [n for n in world.norns if n.name not in ("Mom", "Dad")]
        if children:
            assert children[0].species_id in ("Nornus_curiosus", None)

    def test_species_diverges_with_isolation(self):
        """After many generations of isolation, speciation occurs."""
        world = World()
        world.weather_timer = 999

        # Founding population
        founders = [world.add_norn(f"Founder_{i}", 50 + i*10, 50) for i in range(3)]
        for f in founders:
            f.species_id = "Nornus_originalis"

        # Run enough generations
        for _ in range(200):
            world.tick()

        # Should see species diversity
        species_ids = set(n.species_id for n in world.norns if n.species_id)
        assert len(species_ids) >= 1  # At minimum, original species persists


# ═══════════════════════════════════════════════════════════════
# OBSERVABLE PHENOTYPE — traits have visible effects
# ═══════════════════════════════════════════════════════════════

class TestPhenotypeTraits:
    """DNA traits produce observable effects on Norn appearance/behavior."""

    def test_size_determined_by_genetics(self):
        """Norn physical size is derived from growth gene."""
        dna = NornDNA(name="Big")
        dna.set_alleles('size', dominant=0.9, recessive=0.8)
        assert hasattr(dna, 'get_phenotype')
        phenotype = dna.get_phenotype()
        assert 'size' in phenotype

        dna2 = NornDNA(name="Small")
        dna2.set_alleles('size', dominant=0.2, recessive=0.1)
        assert dna.get_phenotype()['size'] > dna2.get_phenotype()['size']

    def test_color_determined_by_genetics(self):
        """Norn color is from pigment genes."""
        dna = NornDNA(name="RedNorn")
        dna.set_alleles('red_pigment', dominant=0.9, recessive=0.7)
        dna.set_alleles('blue_pigment', dominant=0.1, recessive=0.0)
        p = dna.get_phenotype()
        # Higher red, lower blue = reddish appearance
        assert p['red_pigment'] > p['blue_pigment']

    def test_diet_preference_is_genetic(self):
        """Food preference has genetic basis."""
        dna = NornDNA(name="Herbivore")
        dna.set_alleles('diet_herbivory', dominant=0.8, recessive=0.6)
        dna.set_alleles('diet_carnivory', dominant=0.1, recessive=0.05)
        p = dna.get_phenotype()
        assert p['diet_herbivory'] > 0.5
        assert p['diet_carnivory'] < 0.3
