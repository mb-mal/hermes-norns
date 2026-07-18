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

## 📦 Установка

### Зависимости

```bash
# Python 3.10+, pip
python3 -m pip install Pillow pytest
```

### Клонирование

```bash
git clone https://github.com/mb-mal/hermes-norns.git
cd hermes-norns
```

### Hermes Agent (опционально — для LLM-мозга)

Hermes Norns использует Hermes Agent CLI для LLM-решений. Установи Hermes Agent согласно [документации](https://hermes-agent.nousresearch.com/docs):

```bash
# Установка Hermes Agent (если ещё не установлен)
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Настроить провайдера (DeepSeek, OpenAI, Anthropic, etc.)
hermes setup
```

После установки Hermes CLI будет доступен как `hermes` в PATH. Игра автоматически вызывает `hermes -z "prompt"` для каждого решения Норна.

## 🚀 Запуск

### Консольный режим (без LLM, работает сразу)

```bash
cd hermes_brain/python

# Новая игра в реальном времени
python3 game.py --new

# N тиков без UI
python3 game.py --new --ticks 500
```

### С LLM-мозгом (Hermes Agent)

```bash
cd hermes_brain/python

# Каждый Норн думает через LLM
python3 game.py --new --llm --ticks 100
```

### Рендер мира (PIL)

```bash
cd hermes_brain/python
python3 game.py --new --render
# → ~/norns_screenshot.png
```

### Сохранения

```bash
# Автосейв каждые 300 тиков → ~/.hermes-norns/saves/autosave.norns
python3 game.py --new

# Загрузить
python3 game.py --load autosave

# Список сохранений
python3 game.py --list-saves
```

### Тесты

```bash
cd hermes_brain
python3 -m pytest tests/ -v
```

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

## 📄 Лицензия

LGPL v2 (наследовано от openc2e)
