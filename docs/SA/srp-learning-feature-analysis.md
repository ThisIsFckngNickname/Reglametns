# SRP — Анализ фичи: «Обучение на документах компании» (v2 — Paragraph Logic Profile)

> **Проект**: Service for Regulations and Policies (SRP)
> **Версия**: 1.0.0 — Redesign: Paragraph Logic Profile
> **Дата**: 2026-07-04
> **Аудитория**: PM, BE, FE
> **Статус**: Анализ (полная замена предыдущей версии)

---

## Оглавление

1. [Проблема: почему Style Profile недостаточен](#1-проблема-почему-style-profile-недостаточен)
2. [Paragraph Logic Analysis — метод](#2-paragraph-logic-analysis--метод)
3. [Формат вывода: Paragraph Logic Profile](#3-формат-вывода-paragraph-logic-profile)
4. [Интеграция с multi-stage генерацией](#4-интеграция-с-multi-stage-генерацией)
5. [План реализации](#5-план-реализации)
6. [Модель данных](#6-модель-данных)
7. [API контракты](#7-api-контракты)
8. [Изменения во frontend](#8-изменения-во-frontend)
9. [Оценка трудозатрат](#9-оценка-трудозатрат)
10. [Риски](#10-риски)

---

## 1. Проблема: почему Style Profile недостаточен

### 1.1. Что давал Style Profile (предыдущий подход)

Предыдущая версия (v0.4.0) извлекала из документов:

| Аспект | Пример |
|--------|--------|
| Порядок разделов | «Общие положения → Термины → Основной процесс → Контроль» |
| Терминология | Список должностей, ИТ-систем, типов документов |
| Паттерны написания | «Активный залог: [Должность] в [срок] выполняет [действие]» |
| Форматирование | Уровни заголовков, стиль нумерации, наличие таблиц |

**Этого достаточно, чтобы генерировать документ, который выглядит «как надо», но НЕДОСТАТОЧНО, чтобы генерировать ПРАВИЛЬНЫЙ документ по содержанию.**

### 1.2. Что реально ломается в генерации

На практике сгенерированные регламенты имеют следующие дефекты:

| Дефект | Причина | Проявляется |
|--------|---------|-------------|
| **Нет ответственного** | LLM не знает, какие должности отвечают за какие действия | Пункт: «Осуществляется приём ГСМ» вместо «Начальник АЗС осуществляет приём ГСМ» |
| **Нет срока** | LLM не знает типичные дедлайны для шагов | Пункт: «Составляет отчёт» вместо «Составляет отчёт ежемесячно до 5 числа» |
| **Нет метода/системы** | LLM не знает, в каких системах выполняются операции | Пункт: «Оформляет документы» вместо «Оформляет документы в 1С:Предприятие» |
| **Условная логика отсутствует** | LLM не знает типичные условия-ветвления | Пункт: «Проводит инвентаризацию» вместо «При отклонении более 5% проводит внеплановую инвентаризацию» |
| **Перекрёстные ссылки не работают** | LLM не знает, как разделы ссылаются друг на друга | Раздел 3 ссылается на несуществующий пункт 4.2 |
| **Consequence отсутствует** | LLM не знает, что бывает за невыполнение | Нет «В случае нарушения — дисциплинарная ответственность» |

### 1.3. Корневая причина

Style Profile описывает **форму** документа (как выглядит), но не описывает **логику построения шагов** (как устроен каждый параграф). Хороший регламент — это не просто красивый документ, это набор инструкций, где для каждого шага определено:

- **КТО** делает (роль/должность)
- **ЧТО** делает (действие)
- **КОГДА** делает (срок/дедлайн)
- **КАК** делает (метод/система)
- **ПРИ КАКОМ УСЛОВИИ** (ветвление)
- **КАКОЙ ДОКУМЕНТ** создаёт
- **ЧТО БУДЕТ** если не сделает (последствие)

**Paragraph Logic Profile** извлекает именно эту логическую структуру — не «как документ выглядит», а «как документ работает».

---

## 2. Paragraph Logic Analysis — метод

### 2.1. Общий поток

```
Загруженные .docx
       │
       ▼
┌─────────────────────────────────────────┐
│ Фаза A: Извлечение параграфов (python-docx) │
│ - Разбить документ на параграфы          │
│ - Определить тип: заголовок / тело / таблица │
│ - Исключить заголовки, оглавления        │
└──────────────────┬──────────────────────┘
                   │ список параграфов (plain text)
                   ▼
┌─────────────────────────────────────────┐
│ Фаза B: LLM-анализ параграфов (батчами)   │
│ - Отправить группы по 5-10 параграфов    │
│ - Извлечь: {role, action, deadline,      │
│   method, condition, document, consequence} │
│ - Для каждого параграфа — 0..N логических │
│   шагов (один параграф может содержать   │
│   несколько шагов)                       │
└──────────────────┬──────────────────────┘
                   │ массив Step[] на документ
                   ▼
┌─────────────────────────────────────────┐
│ Фаза C: Синтез Paragraph Logic Profile    │
│ - Аггрегировать все Step[] по документам │
│ - Извлечь шаблоны предложений (templates) │
│ - Извлечь типовые последовательности      │
│ - Извлечь переходы между параграфами      │
│ - Извлечь section_patterns               │
└──────────────────┬──────────────────────┘
                   │ JSON Profile (2-8 KB)
                   ▼
         Сохраняется в company_profiles
         Используется в multi-stage промптах
```

### 2.2. Фаза A: Извлечение параграфов (python-docx)

```python
def extract_paragraphs(docx_path: str) -> list[ParagraphInfo]:
    """
    Извлечь все параграфы из .docx с метаданными.
    
    Returns:
        Список словарей:
        [
            {
                "index": 0,
                "text": "Начальник АЗС осуществляет приём ГСМ...",
                "style": "Normal",
                "is_heading": False,
                "heading_level": 0,
                "is_list_item": False,
                "list_style": None,  # "bullet" | "number" | None
                "is_table_cell": False,
                "table_info": None,
                "section_idx": 2,  # к какому разделу относится
                "section_title": "3.2 Приём ГСМ",
                "char_count": 312
            },
            ...
        ]
    """
```

**Критические правила фильтрации:**
- Заголовки (Heading 1-4) — исключаются из анализа (они задают структуру, не логику)
- Пустые параграфы — исключаются
- Параграфы < 20 символов — исключаются (вероятно, подпись, номер, разделитель)
- Таблицы — каждый ряд таблицы обрабатывается как отдельный параграф (concatenated cells)
- Нумерованные/маркированные списки — каждый item как отдельный параграф

### 2.3. Фаза B: LLM-анализ параграфов (батчами)

**Почему батчами, а не по одному:**
1. Эффективность: один вызов на 5-10 параграфов вместо N вызовов
2. Контекст: LLM лучше видит логическую связку между соседними параграфами
3. Экономия токенов: один system prompt на всю группу

#### Параметры вызова

| Параметр | Значение |
|----------|----------|
| Температура | 0.1 (минимум творчества, максимум извлечения) |
| max_tokens | 2048 на группу |
| Размер группы | 5-10 параграфов (оптимизация: не более 3000 токенов текста на группу) |
| Модель | Любая доступная (предпочтительно Groq/YandexGPT — качественнее извлекают) |

#### Prompt для LLM (Фаза B)

```
Ты — анализатор корпоративных регламентов. Твоя задача — извлечь ЛОГИЧЕСКУЮ СТРУКТУРУ
из каждого параграфа документа.

Для КАЖДОГО параграфа определи, какие логические шаги (steps) в нём описаны.
Один параграф может содержать 0, 1 или несколько шагов.

Каждый шаг описывается набором полей (все опциональны, но чем больше заполнено — тем лучше):

1. role — КТО выполняет действие? (должность, роль, подразделение)
   Примеры: "Начальник АЗС", "Бухгалтер", "Оператор", "Комиссия"
   Если роль не указана явно — оставь null.

2. action — ЧТО нужно сделать? (глагол + объект)
   Примеры: "осуществляет приём ГСМ", "составляет отчёт", "проверяет соответствие"
   Глагол в форме настоящего времени (что делает?).

3. deadline — КОГДА? (срок, периодичность, дедлайн)
   Примеры: "ежедневно до 10:00", "в течение 3 рабочих дней",
            "не позднее 5 числа каждого месяца", "ежеквартально"
   Извлекай КОНКРЕТНЫЙ срок, не обобщай.

4. method — КАК? (инструмент, система, способ)
   Примеры: "в системе 1С:Предприятие", "на бумажном носителе",
            "посредством электронной почты", "путём прямого измерения"
   Если способ не указан — оставь null.

5. condition — ПРИ КАКОМ УСЛОВИИ? (триггер, ветвление)
   Примеры: "при отклонении более 5%", "в случае несоответствия",
            "если уровень топлива ниже минимального", "по требованию руководства"
   Если условия нет — null.

6. document — КАКОЙ ДОКУМЕНТ создаётся/передаётся?
   Примеры: "акт приёма-передачи", "журнал учёта ГСМ",
            "служебная записка", "отчёт о движении"
   Если документ не упомянут — null.

7. consequence — ЧТО БУДЕТ при нарушении/невыполнении?
   Примеры: "налагается дисциплинарное взыскание", "материальная ответственность",
            "приостановка операции", "повторная проверка"
   Если последствия нет — null.

ВАЖНЫЕ ПРАВИЛА:
1. Если параграф не содержит инструкций (например, общее описание, преамбула) — верни steps: [].
2. Если один параграф содержит несколько шагов (например, список) — создай отдельный step на каждый.
3. Извлекай ТОЛЬКО то, что ЯВНО написано. Не додумывай и не обобщай.
4. Сохраняй оригинальную терминологию (не заменяй "Начальник АЗС" на "руководитель").
5. deadline извлекай с предлогами: "в течение", "до", "не позднее".

Вот параграфы для анализа:

--- ПАРАГРАФ 1 ---
{text параграфа 1}

--- ПАРАГРАФ 2 ---
{text параграфа 2}

...

Ответ верни в строгом JSON-формате (массив объектов):
{
  "paragraphs": [
    {
      "index": 0,
      "steps": [
        {
          "role": "Начальник АЗС",
          "action": "осуществляет приём ГСМ",
          "deadline": "ежедневно до 10:00",
          "method": "в системе 1С:Предприятие",
          "condition": null,
          "document": "акт приёма-передачи",
          "consequence": null
        }
      ]
    },
    ...
  ]
}
```

#### Примеры работы анализатора

**Параграф-источник:**
> Начальник АЗС осуществляет приём ГСМ ежедневно до 10:00 с обязательной фиксацией в системе 1С:Предприятие. При отклонении фактического объёма от документального более 5% составляется акт расхождений.

**Результат (2 steps):**

```json
{
  "index": 5,
  "steps": [
    {
      "role": "Начальник АЗС",
      "action": "осуществляет приём ГСМ",
      "deadline": "ежедневно до 10:00",
      "method": "в системе 1С:Предприятие",
      "condition": null,
      "document": null,
      "consequence": null
    },
    {
      "role": "Начальник АЗС",
      "action": "составляет акт расхождений",
      "deadline": null,
      "method": null,
      "condition": "при отклонении фактического объёма от документального более 5%",
      "document": "акт расхождений",
      "consequence": null
    }
  ]
}
```

### 2.4. Фаза C: Синтез Paragraph Logic Profile

После того как все параграфы всех документов проанализированы, запускается **финальный синтез** — извлечение обобщённых паттернов.

**Вход:** массив `AnalyzedDocument[]` — все распознанные шаги по всем документам.

**Выход:** `ParagraphLogicProfile` (JSON-объект).

Синтез выполняется **одним LLM-вызовом** (температура 0.3, макс 2048 токенов) со следующим промптом:

```
Ты — методолог корпоративных документов. Проанализируй массив распознанных
логических шагов из регламентов компании и синтезируй ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ.

Вот данные анализа {N} документов: всего {M} шагов.

Проанализированные шаги (в формате JSON):
{steps_json[:4000]}

Извлеки в строгом JSON (без пояснений):

1. step_templates — 2-5 наиболее частотных шаблонов предложений с плейсхолдерами.
   Определи ОБЩУЮ ФОРМУЛУ, по которой строятся шаги.
   Пример: "[Должность] [действие] в срок [срок] посредством [способ]"
   Или: "При [условие] [должность] обязан [действие] в течение [срок]"

2. vocabulary — словарь терминов, сгруппированный по категориям:
   - roles: все уникальные должности/роли (с частотностью)
   - actions: все уникальные действия (с частотностью)
   - deadlines: типичные сроки (сгруппировать по типу: периодичность, дедлайн, длительность)
   - methods: все упомянутые системы/способы
   - conditions: типичные условия-триггеры
   - documents: типы документов
   - consequences: типичные последствия

3. logic_rules — правила, описывающие типичную структуру шага:
   - "role_required": true/false — обязательна ли роль в шаге
   - "deadline_required": true/false — обязателен ли срок
   - "typical_order": ["role", "action", "deadline", "method"] — порядок элементов в шаге
   - "conditional_logic": true/false — часто ли используются условия
   - "has_consequences": true/false — есть ли последствия

4. section_patterns — паттерны для разных типов разделов:
   - какие роли типичны для раздела "Ответственность"
   - какие сроки типичны для раздела "Контроль"
   - и т.д.

5. transition_patterns — типичные фразы-связки между параграфами:
   Примеры: "Во исполнение п. X...", "На основании...", "В случае...", "При этом..."

Ответ строго в JSON:
{
  "version": 2,
  "source_document_count": 3,
  "total_steps_analyzed": 245,
  "step_templates": [...],
  "vocabulary": {
    "roles": {"Начальник АЗС": 12, "Бухгалтер": 8, ...},
    "actions": {"осуществляет приём": 10, "составляет отчёт": 7, ...},
    "deadlines": [...],
    "methods": [...],
    "conditions": [...],
    "documents": [...],
    "consequences": [...]
  },
  "logic_rules": {...},
  "section_patterns": {...},
  "transition_patterns": [...]
}
```

### 2.5. Резервный метод: если LLM недоступен или ошибка

Если Фаза B или C не могут выполниться (нет LLM, ошибка провайдера):

1. **Фаза B fallback:** Регулярные выражения на русском:
   - Поиск шаблона «[Должность] [глагол]» — извлечение role+action
   - Поиск паттернов сроков: «в течение \d+», «ежедневно», «ежемесячно», «до \d+:\d+»
   - Поиск паттернов условий: «при [сущ]», «в случае [сущ]», «если»
   - Качество ниже LLM, но базовое извлечение работает

2. **Фаза C fallback:** Статистический анализ:
   - Простейшие шаблоны: "Роль + глагол" если >50% шагов содержат role
   - Словарь: просто уникальные значения
   - Без logic_rules и section_patterns

3. Если оба метода недоступны — профиль создаётся пустым, генерация идёт без обучения.

---

## 3. Формат вывода: Paragraph Logic Profile

### 3.1. Полная JSON-схема

```json
{
  "version": 2,
  "profile_type": "paragraph_logic",
  
  "source_documents": {
    "count": 3,
    "ids": ["uuid-1", "uuid-2", "uuid-3"]
  },
  
  "analysis_stats": {
    "total_paragraphs": 540,
    "total_steps": 245,
    "paragraphs_with_role_pct": 78.5,
    "paragraphs_with_deadline_pct": 62.3,
    "paragraphs_with_method_pct": 45.1,
    "paragraphs_with_condition_pct": 31.2,
    "paragraphs_with_document_pct": 38.7,
    "paragraphs_with_consequence_pct": 12.4,
    "avg_steps_per_paragraph": 1.3
  },

  "step_templates": [
    {
      "pattern": "[role] [action] в срок [deadline] посредством [method]",
      "frequency": "high",
      "example": "Начальник АЗС осуществляет приём ГСМ в срок ежедневно до 10:00 посредством системы 1С:Предприятие",
      "fill_rate": {
        "role": 1.0,
        "action": 1.0,
        "deadline": 0.85,
        "method": 0.72
      }
    },
    {
      "pattern": "При [condition] [role] обязан [action] в течение [deadline]",
      "frequency": "medium",
      "example": "При отклонении более 5% Начальник АЗС обязан составить акт расхождений в течение 1 рабочего дня",
      "fill_rate": {
        "condition": 1.0,
        "role": 0.92,
        "action": 1.0,
        "deadline": 0.78
      }
    },
    {
      "pattern": "[role] [action] с оформлением [document]",
      "frequency": "medium",
      "example": "Бухгалтер производит сверку с оформлением акта сверки",
      "fill_rate": {
        "role": 0.95,
        "action": 1.0,
        "document": 0.88
      }
    }
  ],

  "vocabulary": {
    "roles": {
      "items": {
        "Начальник АЗС": {"count": 12, "sections": ["Приём ГСМ", "Контроль", "Ответственность"]},
        "Бухгалтер": {"count": 8, "sections": ["Учёт", "Отчётность"]},
        "Оператор": {"count": 6, "sections": ["Приём ГСМ", "Отпуск ГСМ"]},
        "Главный инженер": {"count": 4, "sections": ["Контроль"]},
        "Комиссия": {"count": 3, "sections": ["Инвентаризация"]}
      },
      "total_unique": 12
    },
    "actions": {
      "items": {
        "осуществляет приём": {"count": 10, "typical_role": "Начальник АЗС"},
        "составляет отчёт": {"count": 7, "typical_role": "Бухгалтер"},
        "проверяет соответствие": {"count": 5, "typical_role": "Главный инженер"},
        "производит отпуск": {"count": 4, "typical_role": "Оператор"},
        "проводит инвентаризацию": {"count": 3, "typical_role": "Комиссия"}
      },
      "total_unique": 28
    },
    "deadlines": {
      "periodic": ["ежедневно", "еженедельно", "ежемесячно", "ежеквартально"],
      "absolute": ["до 10:00", "до 5 числа каждого месяца", "до 31 декабря"],
      "relative": ["в течение 1 рабочего дня", "в течение 3 рабочих дней", "не позднее 2 часов"],
      "total_unique": 15
    },
    "methods": {
      "systems": ["1С:Предприятие", "1С:Документооборот", "Корпоративная почта"],
      "tools": ["на бумажном носителе", "в электронном виде", "путём прямого измерения"],
      "total_unique": 8
    },
    "conditions": {
      "deviation": ["при отклонении более 5%", "при несоответствии нормам"],
      "event": ["в случае аварии", "при выявлении нарушений", "по требованию руководства"],
      "state": ["если уровень топлива ниже минимального", "при отсутствии подписанных документов"],
      "total_unique": 12
    },
    "documents": {
      "types": ["акт приёма-передачи", "журнал учёта ГСМ", "счёт-фактура", "служебная записка", "акт сверки"],
      "total_unique": 10
    },
    "consequences": {
      "disciplinary": ["дисциплинарное взыскание", "выговор", "замечание"],
      "material": ["материальная ответственность", "удержание из зарплаты"],
      "process": ["приостановка операции", "повторная проверка", "отстранение от работы"],
      "total_unique": 7
    }
  },

  "logic_rules": {
    "role_required": true,
    "deadline_required": false,
    "method_required": false,
    "condition_frequency": "medium",
    "consequence_frequency": "low",
    
    "typical_step_order": ["role", "action", "deadline", "method", "condition", "document", "consequence"],
    
    "section_defaults": {
      "Общие положения": {
        "expected_step_types": [],
        "description": "Только текст, без шагов"
      },
      "Порядок действий": {
        "expected_step_types": ["role", "action", "deadline", "method"],
        "min_steps": 5
      },
      "Контроль": {
        "expected_step_types": ["role", "action", "condition", "consequence"],
        "min_steps": 3
      },
      "Ответственность": {
        "expected_step_types": ["role", "consequence"],
        "min_steps": 2
      },
      "Отчётность": {
        "expected_step_types": ["role", "action", "deadline", "document"],
        "min_steps": 2
      }
    },
    
    "mandatory_fields_by_section": {
      "Порядок действий": ["role", "action"],
      "Контроль": ["role", "action", "condition"],
      "Ответственность": ["role", "consequence"]
    }
  },

  "section_patterns": {
    "Планирование": {
      "typical_roles": ["Начальник отдела", "Главный инженер"],
      "typical_deadlines": ["до 15 декабря предшествующего года", "ежеквартально"],
      "template_index": 1
    },
    "Организация работ": {
      "typical_roles": ["Начальник АЗС", "Оператор"],
      "typical_deadlines": ["ежедневно до 10:00", "в течение 2 рабочих дней"],
      "template_index": 0
    },
    "Контроль": {
      "typical_roles": ["Главный инженер", "Комиссия"],
      "typical_conditions": ["при отклонении более 5%", "в случае несоответствия"],
      "template_index": 1
    },
    "Отчётность": {
      "typical_roles": ["Бухгалтер", "Начальник АЗС"],
      "typical_documents": ["отчёт о движении ГСМ", "акт сверки"],
      "template_index": 2
    },
    "Ответственность": {
      "typical_roles": ["Начальник АЗС", "Бухгалтер", "Оператор"],
      "typical_consequences": ["дисциплинарное взыскание", "материальная ответственность"],
      "template_index": null
    }
  },

  "transition_patterns": [
    {
      "phrase": "Во исполнение пункта [n]",
      "usage": "между разделами",
      "example": "Во исполнение пункта 3.2 настоящего Регламента"
    },
    {
      "phrase": "На основании [document]",
      "usage": "начало шага",
      "example": "На основании акта приёма-передачи"
    },
    {
      "phrase": "В случае [condition]",
      "usage": "ветвление внутри шага",
      "example": "В случае несоответствия фактического объёма"
    },
    {
      "phrase": "При этом",
      "usage": "дополнение к предыдущему шагу",
      "example": "При результаты проверки фиксируются в журнале"
    }
  ]
}
```

### 3.2. Ключевые отличия от Style Profile v1

| Аспект | Style Profile v1 (устарел) | Paragraph Logic Profile v2 (новый) |
|--------|---------------------------|-------------------------------------|
| **Фокус** | Форма документа | Логика параграфов |
| **Единица анализа** | Весь документ целиком | Каждый параграф отдельно |
| **Извлекает** | Заголовки, термины, формат | Кто/что/когда/как/при каком условии |
| **Тип анализа** | 1 LLM-вызов на весь документ | N LLM-вызовов (по батчам) + 1 синтез |
| **Размер профиля** | ~2-5 KB | ~4-12 KB |
| **Проверка качества** | Субъективная (похож ли стиль) | Объективная (есть ли role/action/deadline) |
| **Применение в генерации** | "Пиши как в этих документах" | "Для каждого шага укажи role+action+deadline" |
| **Измеряемый эффект** | Слабо | Сильно (можно проверить fill rate) |

---

## 4. Интеграция с multi-stage генерацией

### 4.1. Как профиль входит в каждый этап

#### Stage 1: План (Planner)

Добавляется в system_prompt:

```
===== ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ КОМПАНИИ =====

Для каждого раздела укажи, какие поля должны быть в шагах:

- Общие положения: только текст, шаги не нужны
- Организация работ: role + action + deadline + method
- Контроль: role + action + condition + consequence
- Ответственность: role + consequence
- Отчётность: role + action + deadline + document

Типичные роли в разделах:
- Организация работ: Начальник АЗС, Оператор
- Контроль: Главный инженер, Комиссия
- Отчётность: Бухгалтер

Минимальное количество шагов в разделе:
- Организация работ: 5
- Контроль: 3
- Отчётность: 2
```

**Эффект:** Планер сразу генерирует структуру с правильным распределением полей по разделам.

#### Stage 2: Аннотации (Annotator)

Добавляется в system_prompt:

```
===== ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ КОМПАНИИ =====

Словарь терминов компании:
- Должности: Начальник АЗС, Бухгалтер, Оператор, Главный инженер, Комиссия
- Системы: 1С:Предприятие, 1С:Документооборот
- Документы: акт приёма-передачи, журнал учёта ГСМ, счёт-фактура
- Сроки: ежедневно до 10:00, в течение 3 рабочих дней, до 5 числа

Типичные условия: при отклонении более 5%, в случае несоответствия, по требованию руководства
Типичные последствия: дисциплинарное взыскание, материальная ответственность
```

**Эффект:** Аннотатор использует РЕАЛЬНУЮ терминологию компании, а не generic.

#### Stage 3: Генерация (Writer)

Добавляется в system_prompt:

```
===== ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ КОМПАНИИ =====

СТРОГО соблюдай следующие шаблоны построения параграфов:

[ШАБЛОН 1] — для шагов Организация работ
  "[role] [action] в срок [deadline] посредством [method]"
  Пример: "Начальник АЗС осуществляет приём ГСМ в срок ежедневно до 10:00 
           посредством системы 1С:Предприятие"

[ШАБЛОН 2] — для шагов Контроль
  "При [condition] [role] обязан [action] в течение [deadline]"
  Пример: "При отклонении более 5% Начальник АЗС обязан составить акт расхождений 
           в течение 1 рабочего дня"

[ШАБЛОН 3] — для шагов Отчётность
  "[role] [action] с оформлением [document] в срок [deadline]"
  Пример: "Бухгалтер производит сверку с оформлением акта сверки в срок до 5 числа 
           каждого месяца"

ВАЖНЫЕ ПРАВИЛА:
1. Каждый шаг должен содержать роль (КТО) и действие (ЧТО).
2. Если в профиле указан типичный срок для действия — используй его.
3. Если действие типично выполняется в системе — укажи систему.
4. Для раздела "Контроль" ОБЯЗАТЕЛЬНО укажи условие и последствие.
5. Для раздела "Ответственность" укажи роль и последствие.
```

**Эффект:** Генератор пишет шаги по РЕАЛЬНЫМ шаблонам компании, с правильными ролями, сроками, методами.

#### Stage 4: Аудит (Auditor)

Добавляется в system_prompt:

```
===== ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ КОМПАНИИ =====

Проверь каждый шаг сгенерированного раздела:

Для раздела "Организация работ":
- [ ] Есть role (должность)? Должна быть одна из: Начальник АЗС, Оператор, Бухгалтер
- [ ] Есть action (глагол в настоящем времени)?
- [ ] Есть deadline (срок)? Хотя бы "ежедневно", если не указан конкретный
- [ ] Есть method (система/способ)? Если в профиле указана система для этого действия

Для раздела "Контроль":
- [ ] Есть role?
- [ ] Есть action?
- [ ] Есть condition (условие)?
- [ ] Есть consequence (последствие)?

Для раздела "Ответственность":
- [ ] Есть role?
- [ ] Есть consequence?

Общие проверки:
- [ ] Нет пассивного залога (должен быть активный: "Начальник АЗС осуществляет", а не "Осуществляется")
- [ ] Терминология соответствует профилю (должности, системы, документы)
- [ ] Использованы шаблоны из профиля

Верни JSON с результатами проверки каждого шага.
```

**Эффект:** Аудитор объективно проверяет каждый шаг на наличие обязательных полей.

### 4.2. Оценка расхода токенов на этап

| Компонент | Размер |
|-----------|--------|
| Базовый system prompt | ~500-800 токенов |
| Блок Paragraph Logic Profile | **~400-1200 токенов** |
| Итого overhead | **~400-1200 токенов** (~3-7% от лимита 32K) |

### 4.3. Обратная совместимость

- Если `company_profile_id` не указан — генерация идёт как сейчас (без обучения)
- Если профиль имеет `profile_type: "paragraph_logic"` — применяется Paragraph Logic Profile
- Если профиль имеет `profile_type: "style_profile"` (старый) — применяется старый Style Profile
- Если LLM-анализ не удался — профиль создаётся пустым с `status = "failed"`, генерация без обучения

---

## 5. План реализации

### 5.1. Общая архитектура

```
┌──────────────┐    POST /api/company-profiles/upload     ┌──────────────────────────┐
│ Пользователь  │  ──────────────────────────────────────>  │     Backend: FastAPI      │
│ (React UI)   │                                           │                          │
│              │ <── 201 { profile_id }                     │ 1. Сохранить .docx       │
│              │                                           │ 2. Создать профиль       │
│              │    POST /api/company-profiles/{id}/analyze │                          │
│              │  ──────────────────────────────────────>  │ 3. Background задача:    │
│              │ <── 202 { status: "analyzing" }            │    Фаза A: python-docx   │
│              │                                           │    → параграфы            │
│              │    GET /api/company-profiles/{id}          │    Фаза B: LLM батчи     │
│              │  ──────────────────────────────────────>  │    → Step[] на параграф   │
│              │ <── { profile_json, status: "ready" }     │    Фаза C: LLM синтез    │
│              │                                           │    → ParagraphLogicProfile│
│              │    POST /api/generate/multi                │                          │
│              │    { topic, company_profile_id }           │ 4. Сохранить профиль в БД │
│              │  ──────────────────────────────────────>  └──────────┬───────────────┘
│              │                                                      │
│              │                                           ┌──────────┴───────────────┐
│              │                                           │  Multi-Stage Pipeline     │
│              │                                           │  Stage 1-4: system_prompt │
│              │                                           │  += PARAGRAPH_LOGIC_BLOCK │
│              │                                           └──────────────────────────┘
```

### 5.2. Этапы реализации

#### Stage 6.1: Модели и CRUD (1 день)

**Что входит:**
- SQLAlchemy модели: `CompanyProfile` (с полем `profile_type`) + `UploadedDocument`
- Alembic/авто-миграция
- Pydantic схемы
- CRUD-сервис для профилей
- Сохранение .docx на диск
- **Изменение** `profile_json` — добавить поле `profile_type: "paragraph_logic" | "style_profile"`

**Файлы:**
- `backend/app/models/company_profile.py`
- `backend/app/models/uploaded_document.py`
- `backend/app/schemas/company_profile.py`
- `backend/app/services/company_profile_service.py`

#### Stage 6.2: Фаза A — Извлечение параграфов (2 дня)

**Что входит:**
- Модуль `paragraph_extractor.py`: python-docx → список параграфов с метаданными
- Фильтрация: исключение заголовков, пустых параграфов, коротких строк
- Обработка таблиц (каждый ряд → параграф)
- Определение section_idx (к какому разделу относится параграф)
- Тесты на 3 реальных .docx

**Файлы:**
- `backend/app/services/paragraph_extractor.py`

#### Stage 6.3: Фаза B — LLM-анализ параграфов (3 дня)

**Что входит:**
- Модуль `paragraph_analyzer.py`
- Логика батчинга (группы по 5-10 параграфов)
- LLM-промпт для извлечения Step[] (см. раздел 2.3)
- Парсинг JSON-ответа с валидацией
- Fallback на регулярные выражения при ошибке LLM
- Сбор статистики (fill rates по полям)

**Файлы:**
- `backend/app/services/paragraph_analyzer.py`

#### Stage 6.4: Фаза C — Синтез профиля (2 дня)

**Что входит:**
- Модуль `profile_synthesizer.py`
- LLM-промпт для синтеза Paragraph Logic Profile (см. раздел 2.4)
- Построение vocabulary (частотный анализ)
- Построение step_templates (обобщение паттернов)
- Построение logic_rules (правила заполнения по секциям)
- Валидация финального JSON

**Файлы:**
- `backend/app/services/profile_synthesizer.py`

#### Stage 6.5: API эндпоинты (1 день)

**Что входит:**
- 5 новых эндпоинтов (см. раздел 7)
- Изменения в `POST /api/generate/multi` — добавить `company_profile_id`
- Интеграция с multi-stage генератором
- Background-задача анализа

**Файлы:**
- `backend/app/api/company_profile_routes.py`
- Изменения: `backend/app/api/routes.py`, `backend/app/services/generator.py`

#### Stage 6.6: Frontend (2 дня)

**Что входит:**
- Компоненты: `CompanyProfilePanel`, `UploadForm`, `ProfileCard`, `ProfileSelector`
- Вкладка «Профили компании» в App.tsx
- API-функции в client.ts
- Типы в types.ts
- Отображение статуса анализа
- Отображение статистики профиля (fill rates)
- **Новое:** визуализация step_templates (пользователь видит шаблоны)

**Файлы:** (см. раздел 8)

#### Stage 6.7: Тестирование (1 день)

**Что входит:**
- Тестирование на 3-5 реальных .docx регламентах
- Проверка fill rates: role≥80%, action≥90%, deadline≥50%
- Проверка что профиль улучшает генерацию (A/B тест: с профилем и без)
- Edge cases: пустой документ, 1 параграф, таблицы, списки

### 5.3. Итого

| Stage | Дни | Описание |
|-------|-----|----------|
| 6.1 Модели + CRUD | 1 | База для хранения |
| 6.2 Фаза A: Извлечение | 2 | python-docx парсинг |
| 6.3 Фаза B: LLM-анализ | 3 | Основная логика |
| 6.4 Фаза C: Синтез | 2 | Построение профиля |
| 6.5 API | 1 | Эндпоинты + интеграция |
| 6.6 Frontend | 2 | UI |
| 6.7 Тестирование | 1 | QA |
| **Итого** | **~12 дней** | |

---

## 6. Модель данных

### 6.1. Новая таблица: `company_profiles` (расширенная)

```sql
CREATE TABLE IF NOT EXISTS company_profiles (
    id              TEXT PRIMARY KEY,                -- UUID v4
    name            TEXT NOT NULL,                   -- Название профиля (пользовательское)
    description     TEXT DEFAULT '',                 -- Описание (опционально)
    profile_type    TEXT NOT NULL DEFAULT 'paragraph_logic'
                    CHECK(profile_type IN (
                        'paragraph_logic',  -- v2: логика параграфов (НОВЫЙ)
                        'style_profile'     -- v1: стиль документа (устаревший)
                    )),
    document_count  INTEGER DEFAULT 0,               -- Сколько документов загружено
    profile_json    TEXT NOT NULL,                   -- JSON: ParagraphLogicProfile или StyleProfile
    analysis_stats  TEXT,                            -- JSON со статистикой анализа (см. ниже)
    status          TEXT NOT NULL DEFAULT 'uploaded'
                    CHECK(status IN (
                        'uploaded',     -- Загружены документы, анализ не запущен
                        'extracting',   -- Фаза A: извлечение параграфов
                        'analyzing',    -- Фаза B: LLM-анализ параграфов
                        'synthesizing', -- Фаза C: синтез профиля
                        'ready',        -- Анализ завершён, профиль готов
                        'failed'        -- Ошибка анализа
                    )),
    error_message   TEXT,                            -- Ошибка при status='failed'
    progress_pct    INTEGER DEFAULT 0,               -- Прогресс 0-100
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_profiles_status ON company_profiles(status);
CREATE INDEX IF NOT EXISTS idx_profiles_type ON company_profiles(profile_type);
```

**Поле `analysis_stats` (JSON):**

```json
{
  "total_paragraphs": 540,
  "total_steps": 245,
  "paragraphs_analyzed": 540,
  "paragraphs_with_role_pct": 78.5,
  "paragraphs_with_deadline_pct": 62.3,
  "paragraphs_with_method_pct": 45.1,
  "paragraphs_with_condition_pct": 31.2,
  "paragraphs_with_document_pct": 38.7,
  "paragraphs_with_consequence_pct": 12.4,
  "avg_steps_per_paragraph": 1.3,
  "phase_a_duration_sec": 4.2,
  "phase_b_duration_sec": 45.8,
  "phase_c_duration_sec": 12.1,
  "llm_calls_phase_b": 18,
  "llm_calls_phase_c": 1,
  "total_tokens_used": 45200,
  "failed_paragraphs": 2
}
```

### 6.2. Новая таблица: `analyzed_paragraphs`

Эта таблица опциональна и нужна для:
1. Отладки (пользователь может увидеть, как проанализирован каждый параграф)
2. Перегенерации профиля без повторного LLM-вызова (если упала Фаза C)
3. Статистики

```sql
CREATE TABLE IF NOT EXISTS analyzed_paragraphs (
    id              TEXT PRIMARY KEY,                -- UUID v4
    profile_id      TEXT NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES uploaded_documents(id) ON DELETE CASCADE,
    paragraph_index INTEGER NOT NULL,                -- Индекс параграфа в документе
    section_title   TEXT,                            -- Название раздела, к которому относится
    original_text   TEXT NOT NULL,                   -- Исходный текст параграфа
    steps_json      TEXT NOT NULL,                   -- JSON: массив Step[]
    char_count      INTEGER DEFAULT 0,
    is_table_row    INTEGER DEFAULT 0,
    is_list_item    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analyzed_par_profile ON analyzed_paragraphs(profile_id);
CREATE INDEX IF NOT EXISTS idx_analyzed_par_doc ON analyzed_paragraphs(document_id);
```

**Пример `steps_json` для одного параграфа:**

```json
[
  {
    "role": "Начальник АЗС",
    "action": "осуществляет приём ГСМ",
    "deadline": "ежедневно до 10:00",
    "method": "в системе 1С:Предприятие",
    "condition": null,
    "document": null,
    "consequence": null
  },
  {
    "role": null,
    "action": "составляет акт расхождений",
    "deadline": null,
    "method": null,
    "condition": "при отклонении более 5%",
    "document": "акт расхождений",
    "consequence": null
  }
]
```

### 6.3. Новая таблица: `uploaded_documents`

```sql
CREATE TABLE IF NOT EXISTS uploaded_documents (
    id              TEXT PRIMARY KEY,                -- UUID v4
    profile_id      TEXT NOT NULL REFERENCES company_profiles(id) ON DELETE CASCADE,
    original_name   TEXT NOT NULL,                   -- Оригинальное имя файла
    stored_path     TEXT NOT NULL,                   -- Путь к сохранённому .docx
    file_size       INTEGER DEFAULT 0,               -- Размер в байтах
    mime_type       TEXT DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    status          TEXT NOT NULL DEFAULT 'uploaded'
                    CHECK(status IN (
                        'uploaded',     -- Загружен
                        'extracted',    -- Фаза A завершена
                        'analyzed',     -- Фаза B завершена
                        'failed'        -- Ошибка
                    )),
    paragraph_count INTEGER DEFAULT 0,               -- Сколько параграфов извлечено
    step_count      INTEGER DEFAULT 0,               -- Сколько шагов найдено
    extracted_text  TEXT,                            -- Извлечённый текст (кэш)
    analysis_error  TEXT,                            -- Ошибка анализа
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_uploaded_docs_profile ON uploaded_documents(profile_id);
```

### 6.4. Изменения в существующих таблицах

**`generation_sessions`** — добавить колонку:
```sql
ALTER TABLE generation_sessions ADD COLUMN company_profile_id TEXT REFERENCES company_profiles(id);
```

**`documents`** — добавить колонку:
```sql
ALTER TABLE documents ADD COLUMN company_profile_id TEXT REFERENCES company_profiles(id);
ALTER TABLE documents ADD COLUMN profile_type TEXT DEFAULT 'style_profile';
```

### 6.5. SQLAlchemy модели

```python
# app/models/company_profile.py
class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    profile_type = Column(String(20), nullable=False, default="paragraph_logic")
    document_count = Column(Integer, default=0)
    profile_json = Column(Text, nullable=False)  # ParagraphLogicProfile или StyleProfile
    analysis_stats = Column(Text, nullable=True)  # JSON statistics
    status = Column(String(20), nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)
    progress_pct = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    documents = relationship("UploadedDocument", back_populates="profile",
                              cascade="all, delete-orphan")
    analyzed_paragraphs = relationship("AnalyzedParagraph", back_populates="profile",
                                        cascade="all, delete-orphan")


# app/models/analyzed_paragraph.py
class AnalyzedParagraph(Base):
    __tablename__ = "analyzed_paragraphs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="CASCADE"), nullable=False)
    paragraph_index = Column(Integer, nullable=False)
    section_title = Column(Text, nullable=True)
    original_text = Column(Text, nullable=False)
    steps_json = Column(Text, nullable=False)  # JSON array of Step objects
    char_count = Column(Integer, default=0)
    is_table_row = Column(Integer, default=0)
    is_list_item = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    profile = relationship("CompanyProfile", back_populates="analyzed_paragraphs")
    document = relationship("UploadedDocument", back_populates="analyzed_paragraphs")
```

---

## 7. API контракты

### 7.1. POST /api/company-profiles/upload

Загрузить один или несколько .docx файлов как новый профиль (v2).

**Request:** `multipart/form-data`
```
name: "Регламенты ГСМ"                     # Название профиля (optional)
description: "Все регламенты отдела ГСМ"    # Описание (optional)
files: [file1.docx, file2.docx]            # 1-3 .docx файла
```

**Успешный ответ (201):**
```json
{
  "profile_id": "uuid-string",
  "name": "Регламенты ГСМ",
  "profile_type": "paragraph_logic",
  "document_count": 2,
  "status": "uploaded"
}
```

**Ошибки:**

| Код | Ситуация |
|-----|----------|
| 400 | Не .docx файл, файл повреждён, больше 3 файлов |
| 413 | Файл > 10MB |
| 422 | Нет файлов, имя > 200 символов |

### 7.2. POST /api/company-profiles/{profile_id}/analyze

Запустить полный цикл анализа (Фазы A → B → C).

**Request:** пустое тело

**Успешный ответ (202):**
```json
{
  "profile_id": "uuid-string",
  "status": "extracting",
  "estimated_seconds": 90,
  "progress_pct": 0
}
```

**Ошибки:**

| Код | Ситуация |
|-----|----------|
| 404 | Профиль не найден |
| 400 | Профиль уже анализируется или готов |
| 422 | Нет документов в профиле |

**Поток выполнения (background asyncio task):**

```
1. Статус → "extracting" (Фаза A)
   - python-docx: извлечение параграфов для каждого документа
   - Сохранение в analyzed_paragraphs
   - Прогресс: 0-30%

2. Статус → "analyzing" (Фаза B)
   - Для каждой группы параграфов (5-10 шт): LLM-вызов
   - Парсинг ответа, валидация
   - Обновление steps_json в analyzed_paragraphs
   - Прогресс: 30-80%

3. Статус → "synthesizing" (Фаза C)
   - Один LLM-вызов: синтез Paragraph Logic Profile
   - Сохранение в profile_json
   - Статус → "ready" (или "failed")
   - Прогресс: 80-100%
```

### 7.3. GET /api/company-profiles/{profile_id}

Получить детали профиля (включая profile_json и analysis_stats).

**Успешный ответ (200):**
```json
{
  "profile_id": "uuid-string",
  "name": "Регламенты ГСМ",
  "description": "Все регламенты отдела ГСМ",
  "profile_type": "paragraph_logic",
  "document_count": 2,
  "status": "ready",
  "progress_pct": 100,
  "profile_json": { ... },
  "analysis_stats": {
    "total_paragraphs": 540,
    "total_steps": 245,
    "paragraphs_with_role_pct": 78.5,
    "paragraphs_with_deadline_pct": 62.3
  },
  "documents": [
    {
      "id": "uuid",
      "original_name": "Reglament-GSM.docx",
      "file_size": 245760,
      "paragraph_count": 312,
      "step_count": 145,
      "status": "analyzed"
    }
  ],
  "created_at": "2026-07-04T10:00:00",
  "updated_at": "2026-07-04T10:05:00"
}
```

**Ошибки:**

| Код | Ситуация |
|-----|----------|
| 404 | Профиль не найден |

### 7.4. GET /api/company-profiles/{profile_id}/paragraphs

Получить список проанализированных параграфов (для отладки/визуализации).

**Query params:** `section` (фильтр по разделу), `document_id`, `limit` (50), `offset` (0)

**Успешный ответ (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "paragraph_index": 42,
      "section_title": "3.2 Приём ГСМ",
      "original_text": "Начальник АЗС осуществляет приём ГСМ...",
      "char_count": 312,
      "is_table_row": false,
      "is_list_item": false,
      "steps": [
        {
          "role": "Начальник АЗС",
          "action": "осуществляет приём ГСМ",
          "deadline": "ежедневно до 10:00",
          "method": "в системе 1С:Предприятие",
          "condition": null,
          "document": null,
          "consequence": null
        }
      ]
    }
  ],
  "total": 540
}
```

### 7.5. GET /api/company-profiles (список)

```
GET /api/company-profiles?status=ready&profile_type=paragraph_logic&limit=20&offset=0
```

**Успешный ответ (200):**
```json
{
  "items": [
    {
      "profile_id": "uuid",
      "name": "Регламенты ГСМ",
      "profile_type": "paragraph_logic",
      "document_count": 2,
      "status": "ready",
      "progress_pct": 100,
      "created_at": "2026-07-04T10:00:00"
    }
  ],
  "total": 1
}
```

### 7.6. DELETE /api/company-profiles/{profile_id}

Удалить профиль и все связанные документы, параграфы.

**Успешный ответ (200):** `{ "status": "deleted" }`

### 7.7. GET /api/company-profiles/{profile_id}/download/{doc_id}

Скачать оригинальный загруженный .docx файл.

### 7.8. Изменения в POST /api/generate/multi

```json
{
  "topic": "Регламент по учёту ГСМ",
  "provider": "auto",
  "company_profile_id": "uuid-string",     // NEW: опционально
  "generation_mode": "multi"              // без изменений
}
```

Если `company_profile_id` указан:
1. Загружается `profile_json` из CompanyProfile
2. Если `profile_type == "paragraph_logic"` — строится блок PARAGRAPH_LOGIC_BLOCK
3. Если `profile_type == "style_profile"` (старый) — строится старый STYLE_BLOCK
4. Блок добавляется в system_prompt каждого этапа

### 7.9. Новые Pydantic схемы

```python
# app/schemas/company_profile.py

class Step(BaseModel):
    role: Optional[str] = None
    action: Optional[str] = None
    deadline: Optional[str] = None
    method: Optional[str] = None
    condition: Optional[str] = None
    document: Optional[str] = None
    consequence: Optional[str] = None

class AnalyzedParagraphResponse(BaseModel):
    id: str
    paragraph_index: int
    section_title: Optional[str]
    original_text: str
    char_count: int
    is_table_row: bool
    is_list_item: bool
    steps: list[Step]

class AnalysisStats(BaseModel):
    total_paragraphs: int
    total_steps: int
    paragraphs_with_role_pct: float
    paragraphs_with_deadline_pct: float
    paragraphs_with_method_pct: float
    paragraphs_with_condition_pct: float
    paragraphs_with_document_pct: float
    paragraphs_with_consequence_pct: float
    avg_steps_per_paragraph: float
    total_tokens_used: Optional[int] = None

class CompanyProfileResponse(BaseModel):
    profile_id: str
    name: str
    description: Optional[str] = ""
    profile_type: str
    document_count: int
    status: str
    progress_pct: int
    profile_json: Optional[dict] = None
    analysis_stats: Optional[AnalysisStats] = None
    documents: list[UploadedDocSummary]
    created_at: str
    updated_at: str

class ParagraphLogicProfile(BaseModel):
    """Полная схема Paragraph Logic Profile (для валидации)."""
    version: int = 2
    profile_type: str = "paragraph_logic"
    source_documents: dict
    analysis_stats: Optional[dict] = None
    step_templates: list[dict]
    vocabulary: dict
    logic_rules: dict
    section_patterns: dict
    transition_patterns: list[dict]
```

---

## 8. Изменения во frontend

### 8.1. Новые компоненты

| Компонент | Описание | Файл |
|-----------|----------|------|
| `CompanyProfilePanel` | Панель управления профилями | `frontend/src/components/CompanyProfilePanel.tsx` |
| `UploadForm` | Форма загрузки .docx с drag-and-drop | `frontend/src/components/UploadForm.tsx` |
| `ProfileCard` | Карточка профиля: статус, документы, кнопки | `frontend/src/components/ProfileCard.tsx` |
| `ProfileSelector` | Выпадающий список профилей в форме генерации | `frontend/src/components/ProfileSelector.tsx` |
| `TemplateVisualizer` | **NEW:** визуализация шаблонов шагов | `frontend/src/components/TemplateVisualizer.tsx` |
| `StepInspector` | **NEW:** просмотр проанализированных параграфов | `frontend/src/components/StepInspector.tsx` |

### 8.2. TemplateVisualizer

Новый компонент, который показывает пользователю, какие шаблоны шагов извлечены из его документов:

```
┌──────────────────────────────────────────────┐
│  📊 Профиль логики параграфов                 │
│                                               │
│  Статистика:                                  │
│  ■ 78.5% шагов содержат роль                  │
│  ■ 62.3% шагов содержат срок                  │
│  ■ 45.1% шагов содержат метод                 │
│                                               │
│  Шаблоны шагов:                               │
│  ┌──────────────────────────────────────┐     │
│  │ [Должность] [действие] в срок [срок] │     │
│  │ посредством [способ]                  │     │
│  │ Частота: ●●●●●●○○○○ (высокая)        │     │
│  │ Пример: Начальник АЗС осуществляет   │     │
│  │ приём ГСМ в срок ежедневно до 10:00  │     │
│  │ посредством системы 1С:Предприятие   │     │
│  └──────────────────────────────────────┘     │
│                                               │
│  Словарь терминов:                            │
│  🧑‍💼 Должности: Начальник АЗС, Бухгалтер...   │
│  🖥️ Системы: 1С:Предприятие, 1С:ДО...         │
│  📄 Документы: акт приёма-передачи...          │
│  ⏰ Сроки: ежедневно до 10:00...               │
│  🔄 Условия: при отклонении более 5%...        │
└──────────────────────────────────────────────┘
```

### 8.3. Новые типы (types.ts)

```typescript
// Добавить в frontend/src/types.ts

export interface Step {
  role: string | null;
  action: string | null;
  deadline: string | null;
  method: string | null;
  condition: string | null;
  document: string | null;
  consequence: string | null;
}

export interface ParagraphAnalysis {
  id: string;
  paragraph_index: number;
  section_title: string | null;
  original_text: string;
  char_count: number;
  is_table_row: boolean;
  is_list_item: boolean;
  steps: Step[];
}

export interface AnalysisStats {
  total_paragraphs: number;
  total_steps: number;
  paragraphs_with_role_pct: number;
  paragraphs_with_deadline_pct: number;
  paragraphs_with_method_pct: number;
  paragraphs_with_condition_pct: number;
  paragraphs_with_document_pct: number;
  paragraphs_with_consequence_pct: number;
  avg_steps_per_paragraph: number;
}

export interface StepTemplate {
  pattern: string;
  frequency: 'high' | 'medium' | 'low';
  example: string;
  fill_rate: Record<string, number>;
}

export interface CompanyProfile {
  profile_id: string;
  name: string;
  description?: string;
  profile_type: 'paragraph_logic' | 'style_profile';
  document_count: number;
  status: 'uploaded' | 'extracting' | 'analyzing' | 'synthesizing' | 'ready' | 'failed';
  progress_pct: number;
  profile_json?: any;
  analysis_stats?: AnalysisStats;
  documents: UploadedDocItem[];
  created_at: string;
  updated_at: string;
}

export interface UploadedDocItem {
  id: string;
  original_name: string;
  file_size: number;
  paragraph_count: number;
  step_count: number;
  status: string;
}
```

### 8.4. Новые API-функции (client.ts)

```typescript
// Добавить в frontend/src/api/client.ts

export async function uploadCompanyDocs(
  name: string,
  files: File[],
  description?: string
): Promise<{profile_id: string; name: string; document_count: number; status: string}> { ... }

export async function analyzeProfile(
  profileId: string
): Promise<{profile_id: string; status: string; estimated_seconds: number}> { ... }

export async function getProfile(
  profileId: string
): Promise<CompanyProfile> { ... }

export async function getProfileParagraphs(
  profileId: string,
  params?: { section?: string; document_id?: string; limit?: number; offset?: number }
): Promise<{items: ParagraphAnalysis[]; total: number}> { ... }

export async function listProfiles(
  params?: { status?: string; profile_type?: string; limit?: number; offset?: number }
): Promise<{items: CompanyProfile[]; total: number}> { ... }

export async function deleteProfile(profileId: string): Promise<void> { ... }

export function getProfileDownloadUrl(profileId: string, docId: string): string { ... }
```

### 8.5. Оркестрация UI

```
App.tsx
├── Tab: "Генерация"
│   ├── GeneratorForm.tsx
│   │   ├── ProfileSelector.tsx        ← NEW (выбор профиля обучения)
│   │   └── [existing fields]
│   ├── ProgressPanel.tsx
│   └── ResultPanel.tsx
│
├── Tab: "Профили компании"            ← NEW
│   ├── UploadForm.tsx                 ← NEW
│   └── ProfileCard.tsx                ← NEW
│       ├── Статистика анализа
│       ├── TemplateVisualizer.tsx     ← NEW (шаблоны шагов)
│       ├── StepInspector.tsx          ← NEW (просмотр параграфов)
│       ├── Кнопка "Анализировать"
│       ├── Прогресс-бар анализа
│       └── Кнопка "Удалить"
│
└── Tab: "История"
    └── HistoryList.tsx
```

---

## 9. Оценка трудозатрат

### 9.1. Детальная оценка

| Stage | Задача | Дни | Зависимости |
|-------|--------|-----|-------------|
| **6.1** | Модели + CRUD | 1 | — |
| 6.1.1 | SQLAlchemy модели (3 таблицы) | 0.3 | — |
| 6.1.2 | Pydantic схемы | 0.3 | 6.1.1 |
| 6.1.3 | CRUD-сервис | 0.2 | 6.1.1 |
| 6.1.4 | Сохранение .docx на диск | 0.2 | 6.1.1 |
| **6.2** | Фаза A: Извлечение параграфов | 2 | 6.1 |
| 6.2.1 | `paragraph_extractor.py` — python-docx | 1 | 6.1 |
| 6.2.2 | Фильтрация, обработка таблиц/списков | 0.5 | 6.2.1 |
| 6.2.3 | Определение section_idx | 0.5 | 6.2.1 |
| **6.3** | Фаза B: LLM-анализ параграфов | 3 | 6.2 |
| 6.3.1 | `paragraph_analyzer.py` — батчинг + LLM | 1.5 | 6.2 |
| 6.3.2 | Промпт для извлечения Step[] | 0.5 | 6.3.1 |
| 6.3.3 | Парсинг + валидация JSON | 0.5 | 6.3.1 |
| 6.3.4 | Fallback на регулярки | 0.5 | 6.3.1 |
| **6.4** | Фаза C: Синтез профиля | 2 | 6.3 |
| 6.4.1 | `profile_synthesizer.py` — LLM-синтез | 1 | 6.3 |
| 6.4.2 | Построение vocabulary + templates | 0.5 | 6.4.1 |
| 6.4.3 | Построение logic_rules + section_patterns | 0.5 | 6.4.1 |
| **6.5** | API эндпоинты | 1 | 6.1, 6.2, 6.3, 6.4 |
| 6.5.1 | 5 эндпоинтов профилей | 0.5 | 6.1 |
| 6.5.2 | Background задача анализа | 0.3 | 6.2, 6.3, 6.4 |
| 6.5.3 | Интеграция с multi-stage | 0.2 | 6.4 |
| **6.6** | Frontend | 2 | 6.5 |
| 6.6.1 | UploadForm, ProfileCard | 0.5 | 6.5 |
| 6.6.2 | TemplateVisualizer, StepInspector | 1 | 6.5 |
| 6.6.3 | ProfileSelector + интеграция | 0.5 | 6.5 |
| **6.7** | Тестирование | 1 | 6.5, 6.6 |
| **Итого** | | **~12 дней** | |

### 9.2. Оптимистичная/реалистичная/пессимистичная

| Сценарий | Дни | Условия |
|----------|-----|---------|
| Оптимистичный | 8 | LLM-промпты работают с первого раза, .docx простые |
| Реалистичный | 12 | Стандартные итерации, 1-2 переработки промптов |
| Пессимистичный | 18 | LLM-анализ требует доработки, сложные .docx с таблицами |

---

## 10. Риски

### 10.1. Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|
| **LLM неточно извлекает Step[] (Фаза B)** | Средняя | Высокое | 1. Температура 0.1 — минимум творчества<br>2. JSON-схема в промпте с примерами<br>3. Fallback на регулярные выражения<br>4. Валидация: если role/action null >50% — повторный вызов |
| **LLM галлюцинирует step_templates (Фаза C)** | Средняя | Среднее | 1. Проверка: template содержит только термины из vocabulary<br>2. Температура 0.3<br>3. Возможность ручного редактирования профиля |
| **Большой документ (>100 страниц) — много LLM-вызовов** | Низкая | Среднее | 1. Ограничение: первые 50 страниц (~500 параграфов)<br>2. ~50 LLM-вызовов на большой документ<br>3. Прогресс-бар для пользователя |
| **.docx со сложными таблицами не парсится** | Средняя | Низкое | 1. Объединённые ячейки → fallback<br>2. Таблицы без заголовков → как plain text<br>3. Если не парсится — пропускаем с ошибкой |
| **Профиль не улучшает генерацию** | Средняя | Низкое | 1. A/B тест в Stage 6.7<br>2. Без профиля генерация работает как сейчас |
| **Фазы B/C — таймаут провайдера** | Средняя | Среднее | 1. Fallback на другой провайдер<br>2. Retry 1 раз<br>3. Если всё упало — статус failed, генерация без профиля |
| **Размер profile_json > 12KB** | Низкая | Низкое | 1. Ограничение vocabulary top-20 по частотности<br>2. Не более 5 step_templates |

### 10.2. Продуктовые риски

| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|
| **Пользователь не понимает, что такое "профиль логики"** | Высокая | Среднее | 1. TemplateVisualizer с понятными примерами<br>2. Название в UI: "Стиль компании" (не техническое)<br>3. Подсказки: "Система выучила, как писать шаги в ваших документах" |
| **Fill rates низкие — профиль бесполезен** | Средняя | Среднее | 1. Показывать fill rates в UI<br>2. Если role < 50% — предупреждение "документы содержат мало инструкций"<br>3. Рекомендация загрузить другие документы |
| **Загружены нерегламентные документы** | Средняя | Низкое | 1. Определение типа документа на этапе анализа<br>2. Если не похоже на регламент — предупреждение |

### 10.3. Мониторинг качества (после внедрения)

После Stage 6.7 необходимо замерить:

| Метрика | Ожидание | Метод измерения |
|---------|----------|----------------|
| **role fill rate** в генерации | > 80% шагов содержат роль | Auditor report |
| **deadline fill rate** в генерации | > 50% шагов содержат срок | Auditor report |
| **method fill rate** в генерации | > 40% шагов содержат метод | Auditor report |
| **condition fill rate** (раздел Контроль) | > 70% шагов содержат условие | Auditor report |
| **Улучшение по сравнению с без профиля** | +30% по всем fill rates | A/B тест |
| **Время анализа на 3 документа** | < 120 секунд | Логи |

---

## 11. Открытые вопросы

1. **Как быть с документами, где нет явных ролей (например, техрегламенты)?** Определять на этапе анализа — если role fill rate < 30%, профиль создаётся с `role_required: false` и генерация идёт без требования ролей.

2. **Нужна ли поддержка старого Style Profile (v1)?** Да, для обратной совместимости. Новые профили создаются как `paragraph_logic`, старые читаются как `style_profile`.

3. **Сколько документов оптимально для качественного профиля?** Гипотеза: 2-3 документа по одной теме. Один документ — мало паттернов, >5 — усреднение.

4. **Как часто перезапускать анализ?** Пока только по запросу (кнопка "Анализировать"). В будущем — авто-анализ при загрузке.

5. **Что если один и тот же термин в разных документах используется по-разному?** LLM-синтез (Фаза C) должен усреднять. Если противоречия сильные — профиль использует наиболее частотный вариант.

6. **Нужна ли возможность «закрепить» отдельные шаблоны вручную?** Технически — `PUT /api/company-profiles/{id}` для редактирования profile_json. UI — возможно в будущем.

7. **Поддержка .doc (старый формат)?** Нет. Только .docx. python-docx не поддерживает .doc.

---

## Приложение A: Сравнение подходов v1 vs v2

| Аспект | Style Profile (v1, устарел) | Paragraph Logic Profile (v2, рекомендуется) |
|--------|---------------------------|---------------------------------------------|
| **Фокус анализа** | Структура документа | Логическая структура шагов |
| **Единица** | Весь документ | Каждый параграф |
| **Что извлекает** | Заголовки, термины, формат | Role, Action, Deadline, Method, Condition, Document, Consequence |
| **Метод** | 1 LLM-вызов | N LLM-вызовов (батчи) + 1 синтез |
| **Размер профиля** | ~2-5 KB | ~4-12 KB |
| **Расход токенов на этап** | ~200-400 | ~400-1200 |
| **Fill rate role** | Не измерялся | 78% (цель) |
| **Fill rate deadline** | Не измерялся | 62% (цель) |
| **Сложность реализации** | ★★☆☆☆ (средняя) | ★★★☆☆ (выше средней) |
| **Трудозатраты** | ~5-7 дней | ~12 дней |
| **Эффект на качество** | Средний (стиль) | Высокий (содержание) |

---

## Приложение B: Пример потработы анализатора на реальном параграфе

**Исходный параграф:**
> 3.2.4. Приём ГСМ осуществляется Начальником АЗС ежедневно в период с 8:00 до 10:00. Приём производится в присутствии Оператора АЗС. Факт приёма фиксируется в системе 1С:Предприятие путём формирования акта приёма-передачи ГСМ по форме согласно Приложению №2. В случае выявления расхождений между фактическим и документальным объёмом ГСМ более 5% создаётся комиссия для проведения служебного расследования в течение 2 рабочих дней. По результатам расследования принимается решение о дисциплинарной ответственности виновных лиц.

**Извлечённые Step[]:**

```json
[
  {
    "role": "Начальник АЗС",
    "action": "осуществляет приём ГСМ",
    "deadline": "ежедневно в период с 8:00 до 10:00",
    "method": null,
    "condition": null,
    "document": null,
    "consequence": null
  },
  {
    "role": null,
    "action": "фиксирует факт приёма",
    "deadline": null,
    "method": "в системе 1С:Предприятие",
    "condition": null,
    "document": "акт приёма-передачи ГСМ",
    "consequence": null
  },
  {
    "role": null,
    "action": "создаётся комиссия",
    "deadline": "в течение 2 рабочих дней",
    "method": null,
    "condition": "в случае выявления расхождений более 5%",
    "document": null,
    "consequence": null
  },
  {
    "role": "Комиссия",
    "action": "проводит служебное расследование",
    "deadline": "в течение 2 рабочих дней",
    "method": null,
    "condition": null,
    "document": null,
    "consequence": null
  },
  {
    "role": null,
    "action": "принимается решение",
    "deadline": "по результатам расследования",
    "method": null,
    "condition": null,
    "document": null,
    "consequence": "дисциплинарная ответственность виновных лиц"
  }
]
```

**Извлечённые шаблоны (из этого и других параграфов):**

1. **Шаблон 1:** `[role] осуществляет [action] [deadline]` (высокая частотность)
2. **Шаблон 2:** `В случае [condition] [role] [action] в течение [deadline]` (средняя)
3. **Шаблон 3:** `[action] в системе [method] путём [document]` (средняя)

**Logic rule для раздела "Приём ГСМ":**
- role: required (100% шагов)
- deadline: required (80% шагов)
- method: recommended (60% шагов)
- condition: conditional (только при отклонениях)
- document: recommended (50% шагов)

---

## Приложение C: Миграция с v1 на v2

Для существующих пользователей, у которых уже есть профили v1 (Style Profile):

1. **Обратная совместимость:** Старые профили продолжают работать как `style_profile`
2. **Автоматическая конвертация:** При повторном анализе (кнопка "Анализировать") — старый профиль перезаписывается на `paragraph_logic`
3. **Данные:** Таблица `analyzed_paragraphs` создаётся заново при анализе
4. **Код:** В генераторе — ветвление `if profile_type == "paragraph_logic"` — новый блок, `else` — старый блок

---

*Документ подготовлен: SA, 04.07.2026*
*Статус: готов к ревью PM и передаче BE/FE*
*Полная замена предыдущей версии srp-learning-feature-analysis.md (v0.4.0)*
