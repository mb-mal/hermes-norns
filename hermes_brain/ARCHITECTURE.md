# 🧠 Hermes Norns — Architecture

## What is Creatures?

——Creatures—— (1996, Steve Grand / Creature Labs) — это первая коммерческая игра с настоящим искусственным интеллектом и симуляцией жизни. Игрок выращивает существ — **Норнов** (Norns), — которые обладают:

- **Нейросетевым мозгом** (~1000 нейронов, распределённых по долям/lobes)
- **Биохимией** (эмуляция гормонов, нейромедиаторов, метаболизма)
- **Генетикой** (цифровая ДНК: 700+ генов, мутации, наследование)
- **Способностью к обучению** (Norns учат слова, запоминают объекты, формируют привычки)
- **Полным жизненным циклом** (детство → зрелость → старение, ~40 часов)

В отличие от современных AI-агентов, мозг Норна — это не LLM, а классическая нейросеть с hand-crafted архитектурой: perception lobe → concept lobe → decision lobe, соединённые tract'ами (дендритами) со state-variable правилами (SVRules).

## What is openc2e?

——openc2e—— — это open-source реимплементация игрового движка Creatures на C++. Он воспроизводит:
- Рендеринг мира, физику, CAOS-скрипты (язык объектов/агентов)
- Симуляцию биохимии, генетики и мозга Норнов
- Поддержку всех игр серии (C1, C2, C3, DS)

## Hermes Norns: Vision

Мы заменяем классический нейросетевой мозг (`c2eBrain` с lobes/tracts/SVRules) на **Hermes Brain** — LLM-агент на базе Hermes Agent framework, работающий через CLI и локальные ML-модели на Python.

### Что остаётся от openc2e:
- ✅ Мир, физика, рендеринг
- ✅ Биохимия (гормоны, драйвы, метаболизм)
- ✅ Генетика (ДНК как конфигурация личности агента)
- ✅ CAOS-скрипты для объектов мира
- ✅ Жизненный цикл (возраст, старение, размножение)

### Что заменяется:
- ❌ `c2eBrain` / `c2eLobe` / `c2eTract` / `c2eSVRule`
- ✅ `hermesBrain` — Python-процесс, общающийся через stdin/stdout JSON
- ❌ Фиксированная архитектура нейросети
- ✅ LLM-chain: perception → reasoning → action

## System Architecture

```
┌─────────────────────────────────────────────┐
│                 openc2e Engine (C++)         │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │  World   │  │Biochemistry│  │  Genetics  │ │
│  │ Physics  │  │(hormones) │  │  (DNA)     │ │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│       │              │              │         │
│       ▼              ▼              ▼         │
│  ┌────────────────────────────────────────┐  │
│  │         Perception State                │  │
│  │  { visible_objects, drives, age, ... }  │  │
│  └────────────────┬───────────────────────┘  │
│                   │                           │
│                   │ IPC (Unix socket / pipe)  │
│                   ▼                           │
│  ┌────────────────────────────────────────┐  │
│  │         hermesBrain (C++ bridge)        │  │
│  │  • Serialises perception → JSON        │  │
│  │  • Deserialises action ← JSON          │  │
│  │  • Manages agent process lifecycle     │  │
│  └────────────────┬───────────────────────┘  │
└───────────────────┼──────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│       Hermes Norn Agent (Python)             │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │   hermes_norn_agent.py                │   │
│  │   ┌─────────┐  ┌────────┐  ┌───────┐ │   │
│  │   │Perceive │→│ Reason │→│  Act  │ │   │
│  │   │(prompt) │ │(LLM)   │ │(CAOS) │ │   │
│  │   └─────────┘  └────────┘  └───────┘ │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  Models (local, via llama-cpp / MLX):        │
│  • Reasoning: Llama 3 / Mistral / Qwen      │
│  • Vision: LLaVA / Qwen-VL                  │
│  • Memory: vector DB (ChromaDB)             │
│                                              │
│  Hermes Agent Framework:                     │
│  • Tools: search, memory, terminal          │
│  • Skills: parenting, learning, survival    │
│  • Personality: derived from creature DNA   │
└─────────────────────────────────────────────┘
```

## Perception Pipeline

Каждый тик (~100ms) openc2e собирает состояние Норна:

```json
{
  "creature_id": "norn_42",
  "age_ticks": 15234,
  "life_stage": "adolescent",
  "drives": {
    "hunger": 0.72,
    "thirst": 0.45,
    "fatigue": 0.31,
    "boredom": 0.88,
    "anger": 0.12,
    "fear": 0.05,
    "pain": 0.00,
    "sex_drive": 0.23,
    "crowded": 0.15,
    "loneliness": 0.60
  },
  "biochemistry": {
    "adrenaline": 0.1,
    "cortisol": 0.2,
    "dopamine": 0.7,
    "oxytocin": 0.4
  },
  "visible_objects": [
    {"type": "food", "name": "carrot", "distance": 120, "direction": "left"},
    {"type": "toy", "name": "ball", "distance": 45, "direction": "front"},
    {"type": "norn", "name": "Alice", "distance": 200, "direction": "right"}
  ],
  "recent_memories": [
    "ate a carrot 30 ticks ago — it was tasty",
    "played with ball 150 ticks ago — fun!"
  ],
  "learned_words": {"ball": "toy", "Alice": "creature", "carrot": "food"},
  "dna_traits": {
    "curiosity": 0.8,
    "aggression": 0.2,
    "sociability": 0.7,
    "intelligence": 0.6
  }
}
```

## Action Space

Норн может совершать действия:

| Action | CAOS equivalent | Description |
|---|---|---|
| `APPROACH <object>` | Navigate to object | Подойти к объекту |
| `EAT <object>` | Grab + consume | Съесть еду |
| `PUSH <object>` | Activate 1 | Толкнуть/активировать |
| `PICKUP <object>` | Grab object | Взять в руки |
| `DROP` | Drop | Бросить |
| `SPEAK <word>` | Say | Произнести слово |
| `REST` | Sleep | Лечь спать |
| `PLAY <object>` | Activate toy | Играть с игрушкой |
| `TRAVEL <direction>` | Navigate | Пойти в направлении |
| `BREED <norn>` | Mate | Спариться |
| `QUIET` | Do nothing | Ничего не делать |

## Agent Prompt Template

```
You are a Norn named {name}. You live in the world of Albia.

PERSONALITY (from your DNA):
- Curiosity: {curiosity}/1.0
- Aggression: {aggression}/1.0
- Sociability: {sociability}/1.0
- Intelligence: {intelligence}/1.0

CURRENT STATE:
- Life stage: {life_stage}
- You feel: hungry={hunger} thirsty={thirst} tired={fatigue} bored={boredom}
  lonely={loneliness} scared={fear}

YOU CAN SEE:
{visible_objects_formatted}

WHAT YOU KNOW:
Words you understand: {learned_words}
Recent events: {recent_memories}

DECIDE what to do next. Choose ONE action from the list.
Respond in JSON: {"action": "...", "target": "...", "thought": "..."}
```

## IPC Protocol

C++ ↔ Python communication via Unix domain socket:

```
C++ → Python (every tick):
  {"type": "perception", "tick": N, "data": {...perception...}}

Python → C++ (response):
  {"type": "action", "tick": N, "action": "EAT", "target": "carrot", "thought": "I'm very hungry and there's food nearby"}
```

## Memory System

В отличие от оригинального Creatures (где память — это просто веса нейросети), Hermes Norns используют:

1. **Short-term**: последние N perception→action пар в контексте LLM
2. **Medium-term**: векторная БД (ChromaDB) с embedding'ами событий
3. **Long-term**: сводка личности, усвоенных слов, предпочтений — сохраняется между сессиями

## Development Roadmap

### Phase 1: Standalone Agent (Python CLI)
- [ ] `hermes_norn_agent.py` — принимает JSON perception, возвращает JSON action
- [ ] Prompt engineering для базового поведения (еда, сон, игра)
- [ ] Эмуляция мира в Python (без openc2e) для тестирования
- [ ] DNA → personality traits mapping

### Phase 2: C++ Bridge
- [ ] `hermesBrain` класс в openc2e (implements brain interface)
- [ ] Unix socket IPC между C++ и Python
- [ ] Интеграция с системой драйвов и биохимии

### Phase 3: Memory & Learning
- [ ] ChromaDB для долговременной памяти
- [ ] RAG retrieval при формировании контекста
- [ ] Обучение словам через interaction

### Phase 4: Multi-Agent
- [ ] Несколько Norns с разными личностями
- [ ] Социальное взаимодействие (общение, спаривание)
- [ ] Эмерджентное поведение в популяции

### Phase 5: Vision
- [ ] LLaVA / Qwen-VL для визуального восприятия мира
- [ ] Скриншоты игрового мира → vision-language model → understanding

## Technical Notes

- **Почему CLI, а не REST**: задержка. Тик ~100ms, REST-оверхед съест бюджет. stdin/stdout или Unix socket — sub-ms latency.
- **Почему локальные модели**: офлайн-игра. Никаких API-ключей.
- **Почему не один Python-процесс на всех Norns**: каждый Norn — отдельный агент со своей памятью. Можно shared inference engine.
