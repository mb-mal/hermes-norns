# 🧠 Hermes Norns

**Искусственная жизнь на базе Hermes Agent + современные ML-модели.**

Форк [openc2e](https://github.com/openc2e/openc2e) — open-source движка легендарной игры Creatures (1996, Стив Гранд). Норны получают LLM-мозг вместо классической нейросети.

## 🎯 Что это

Классический Creatures: цифровые существа (Норны) с биохимией, генетикой и нейросетевым мозгом живут в симулированном мире — едят, играют, размножаются, эволюционируют.

**Hermes Norns** заменяет фиксированный нейросетевой мозг на LLM-агента:
- 🧠 Каждый Норн думает через Hermes Agent CLI (DeepSeek / Llama / Qwen)
- 🧬 Менделевская генетика с доминантными/рецессивными аллелями
- 🔬 Мутации при размножении (rate ~2%)
- 📊 Фитнес-отбор средой — разные стратегии → разная выживаемость
- 🌿 Видообразование — изолированные популяции дивергируют
- 🌧️ Погода, растения, порталы, старение и смерть

## 🏗️ Архитектура

```
openc2e Engine (C++)          ← форк, пока не интегрирован
        │
   perception JSON            ← drives, visible objects, weather, nearby_norns
        ▼
perception_v2.py              ← rich prompt: life stage, biochemistry, memories
        │
        ▼
llm_agent.py → Hermes CLI     ← hermes -z "prompt" → JSON action packet
        │
   NornActionPacket            ← валидация: whitelist actions, moods, social
        ▼
world_sim.py                  ← применяет эффекты безопасно
```

## 📦 NornActionPacket — JSON-протокол

LLM возвращает структурированный JSON, который **валидируется** перед применением:

```json
{
  "action": "PLAY",
  "target": "trampoline",
  "thought": "So bored! Trampoline is right there!",
  "mood": "excited",
  "say": "",
  "learn": {},
  "social": {"toward": "Luna", "feeling": "playful"}
}
```

**Защита от галлюцинаций:**
- `action` — whitelist (неизвестное → QUIET)
- `mood` — whitelist из 15 значений
- `social.feeling` — whitelist из 8 значений
- `say` — capped 60 символов
- `learn` — макс 3 записи, значения capped 30 символов
- Неизвестные поля — **дропаются** (нельзя читерить `hunger: 0`)

## 🧬 Эволюция

### Генетика
- 16 traits с аллельными парами (dominant/recessive)
- Менделевское наследование: ребёнок получает случайный аллель от каждого родителя
- Мутации: ±0.25 delta, rate 2%, таргет: dominant/recessive/random

### Фитнес
- +0.01/тик выживания
- Бонусы: сытость +0.005, социализация +0.003
- Разные стратегии → разный фитнес → естественный отбор

### Фенотип
- Размер, цвет (RGB-пигменты), скорость, метаболизм
- Пищевые предпочтения (herbivory/carnivory)
- Всё выводится из генов через `get_phenotype()`

## 🚀 Быстрый старт

```bash
# Клонировать
git clone https://github.com/mb-mal/hermes-norns.git
cd hermes-norns/hermes_brain/python

# Запустить игру (консольный UI)
python3 game.py --new

# Или N тиков без UI
python3 game.py --new --ticks 500

# С LLM-мозгом (требуется Hermes Agent)
python3 game.py --new --llm --ticks 100

# Рендер мира в PNG
python3 game.py --new --render

# Загрузить сохранение
python3 game.py --load autosave

# Тесты
cd .. && python3 -m pytest tests/ -v
```

## 🧪 Тесты

98 тестов, TDD (RED → GREEN → REFACTOR):

| Группа | Тестов | Что проверяет |
|---|---|---|
| `test_v02_features` | 12 | Погода, растения, старение, порталы |
| `test_evolution` | 16 | Мендель, мутации, фитнес, фенотип, видообразование |
| `test_action_packet` | 20 | Валидация JSON, whitelist, парсер, защита от читов |
| `test_packet_world` | 5 | Применение эффектов: речь, обучение, отношения |
| `test_edge_cases` | 45 | Adversarial: null/спуфинг/инъекции/dead norn/memory cap/invisible unicode/10K-char

## 🗺️ Roadmap

- [x] v0.1 — Базовый агент + архитектура
- [x] v0.2 — Мир, мульти-агент, размножение
- [x] v0.3 — Погода, растения, порталы, смерть
- [x] v0.4 — Мендель, мутации, фитнес, фенотип
- [x] v0.5 — JSON-протокол, валидатор, rich perception
- [x] v0.5.1 — 45 adversarial тестов: null/спуфинг/инъекции/dead norn/invisible unicode
- [x] v0.7 — PIL-рендерер мира (vision perception pipeline)
- [x] v0.8 — Multi-agent LLM: batch + parallel Norn decisions
- [x] v0.6 — C++ bridge: IPC-протокол + интеграционный гайд для openc2e
- [x] v1.0 — Игра: save/load, консольный UI, игровой цикл, 104 теста

## 📄 Лицензия

LGPL v2 (наследовано от openc2e)
