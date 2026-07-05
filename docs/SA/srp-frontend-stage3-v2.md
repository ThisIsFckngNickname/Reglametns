# SRP — Frontend Stage 3: Multi-Stage поддержка

> **Проект**: Service for Regulations and Policies (SRP)
> **Версия**: 0.3.0 (Stage 3, v2)
> **Дата**: 2026-07-04
> **Аудитория**: FE (Frontend Engineer)
> **Статус**: Черновик
> **Основание**: Обновление под multi-stage генерацию (Stage 4 backend)

---

## 1. Objective

**Цель:** Модернизировать React-приложение для поддержки multi-stage асинхронной генерации с polling-прогрессом.

**Что даёт пользователю:**
- Выбор между **быстрой синхронной** генерацией (single-stage, legacy) и **качественной многоэтапной** генерацией (multi-stage, recommended)
- **Визуальный прогресс** при multi-stage: видно название этапа, процент выполнения, количество готовых разделов
- **Polling** каждые 3 секунды — страница не замораживается
- Скачивание готового `.docx` после завершения
- История последних 20 генераций с возможностью скачать

**Архитектурный подход:**
- Backend возвращает `202 Accepted` с `generation_id`
- Frontend опрашивает `GET /api/generate/{id}/status` каждые 3 секунды
- Когда `status === "completed"`, появляется ResultPanel с кнопкой скачать
- Пользователь может начать новую генерацию, не дожидаясь завершения текущей (новая просто заменит отслеживаемую)

---

## 2. API Integration

### 2.1. Endpoints (сетка)

| Метод | Endpoint | Назначение | Когда вызывать |
|-------|----------|-----------|----------------|
| `POST` | `/api/generate` | Синхронная генерация (legacy) | Для provider = "ollama" / "groq" / "yandexgpt" |
| `POST` | `/api/generate/multi` | Запуск multi-stage генерации | При нажатии "Generate multi-stage" |
| `GET` | `/api/generate/{id}/status` | Получить статус генерации | Каждые 3 секунды при активной генерации |
| `GET` | `/api/documents` | Список документов (история) | При загрузке страницы |
| `GET` | `/api/documents/{id}/download` | Скачать .docx | По клику "Download" |
| `GET` | `/api/providers` | Список доступных провайдеров | При загрузке страницы |

### 2.2. Контракты

#### POST /api/generate/multi

**Request:**
```json
{
  "topic": "Регламент по учёту ГСМ на АЗС",
  "provider": "auto"
}
```

**Response 202 Accepted:**
```json
{
  "generation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "accepted",
  "estimated_seconds": 600
}
```

**Errors:** 422 (validation), 503 (providers unavailable).

---

#### GET /api/generate/{id}/status

**Response 200 OK (в процессе):**
```json
{
  "generation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generating",
  "current_stage": "generating",
  "stage_name": "Генерация разделов",
  "stage_progress": 60,
  "total_sections": 10,
  "completed_sections": 5,
  "estimated_remaining_seconds": 180,
  "document_id": null,
  "error_message": null,
  "created_at": "2026-07-04T10:00:00Z"
}
```

**Response 200 OK (завершён):**
```json
{
  "generation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "current_stage": "completed",
  "stage_name": "Готово",
  "stage_progress": 100,
  "total_sections": 10,
  "completed_sections": 10,
  "estimated_remaining_seconds": 0,
  "document_id": "doc-uuid-12345",
  "error_message": null,
  "created_at": "2026-07-04T10:00:00Z",
  "completed_at": "2026-07-04T10:12:30Z"
}
```

**Response 200 OK (ошибка):**
```json
{
  "generation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "current_stage": "generating",
  "stage_name": "Генерация разделов",
  "stage_progress": 40,
  "total_sections": 10,
  "completed_sections": 4,
  "estimated_remaining_seconds": 0,
  "document_id": null,
  "error_message": "Провайдер Ollama недоступен: connection refused",
  "created_at": "2026-07-04T10:00:00Z"
}
```

**Маппинг полей:**

| Поле в ответе | Тип | Описание | Комментарий |
|--------------|-----|----------|-------------|
| `generation_id` | string | UUID сессии генерации | — |
| `status` | enum | `accepted` / `planning` / `annotating` / `generating` / `auditing` / `assembling` / `completed` / `failed` | Детальный статус для ProgressPanel |
| `current_stage` | string | Текущий этап (человекочитаемый) | Показывается пользователю |
| `stage_progress` | int (0-100) | Прогресс текущего этапа | Для progress bar |
| `total_sections` | int | Общее количество разделов | Для счётчика |
| `completed_sections` | int | Сколько разделов готово | Для счётчика |
| `estimated_remaining_seconds` | int | Оценка оставшегося времени | Для отображения |
| `document_id` | string|null | ID документа (только когда готов) | Для ссылки скачивания |
| `error_message` | string|null | Сообщение об ошибке | Только при failed |
| `created_at` | string (ISO8601) | Время создания сессии | — |
| `completed_at` | string (ISO8601, null) | Время завершения | Только при completed |

---

#### GET /api/documents

**Response 200 OK:**
```json
[
  {
    "id": "doc-uuid-1",
    "topic": "Регламент по учёту ГСМ",
    "provider_used": "generation",
    "created_at": "2026-07-04T10:12:30Z"
  },
  {
    "id": "doc-uuid-2",
    "topic": "Инструкция по охране труда",
    "provider_used": "ollama",
    "created_at": "2026-07-03T15:00:00Z"
  }
]
```

> **Важно:** Backend возвращает максимум 20 записей, сортировка по `created_at DESC`.

---

#### GET /api/documents/{id}/download

- **Успех (200):** возвращает `.docx` файл с Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- **Ошибка (404):** документ не найден

---

#### GET /api/providers

**Response 200 OK:**
```json
[
  {
    "name": "auto",
    "model": "auto",
    "available": true
  },
  {
    "name": "ollama",
    "model": "qwen2.5:7b",
    "available": true
  },
  {
    "name": "groq",
    "model": "mixtral-8x7b-32768",
    "available": false
  },
  {
    "name": "generation",
    "model": "qwen2.5:7b (multi-stage)",
    "available": true
  }
]
```

> **Важно:** `provider: "generation"` — новый провайдер для multi-stage. Он должен отображаться отдельно или объединяться с auto.

---

### 2.3. Polling logic (описание для FE)

```
function pollGenerationStatus(
  generationId: string,
  onProgress: (status: GenerationStatus) => void,
  intervalMs: number = 3000
): Promise<GenerationStatus>
```

**Алгоритм:**
1. Вызвать `GET /api/generate/{generationId}/status`
2. Вызвать `onProgress(response)` — для обновления UI на каждый ответ
3. Если `response.status === "completed"` или `response.status === "failed"`:
   - Остановить таймер
   - Зарезолвить Promise с финальным статусом
4. Иначе — установить `setTimeout` на `intervalMs` и повторить с шага 1
5. Если ответ 404 (сессия не найдена) — остановить с ошибкой "Generation session not found"
6. Если сетевой таймаут (>10 секунд без ответа) — продолжить polling (не останавливать генерацию)

**Остановка polling при размонтировании компонента:**
- Использовать `AbortController` или флаг `isCancelled`
- В `useEffect` cleanup — сбросить таймер и отменить ожидающий fetch

**Защита от множественных polling:**
- Только один активный polling на момент (проверять `currentGeneration !== null`)
- При старте новой генерации — отменить предыдущий polling (если был)

---

## 3. Types (types.ts)

```typescript
// ============================================================
// Stage 3 — Multi-stage support
// ============================================================

/** Полный статус сессии генерации */
export interface GenerationStatus {
  id: string;
  topic: string;
  status: GenerationStage;
  current_stage: string;       // Человекочитаемое название этапа
  stage_progress: number;      // 0–100
  total_sections: number;
  completed_sections: number;
  provider_used?: string;
  document_id?: string;
  error_message?: string;
  created_at: string;          // ISO8601
  completed_at?: string;       // ISO8601, только при status === "completed"
}

/** Возможные статусы этапов генерации */
export type GenerationStage =
  | 'accepted'
  | 'planning'
  | 'annotating'
  | 'generating'
  | 'auditing'
  | 'assembling'
  | 'completed'
  | 'failed';

/** Информация о документе для списка истории */
export interface DocumentInfo {
  id: string;
  topic: string;
  provider_used: string;
  created_at: string;          // ISO8601
}

/** Информация о доступном AI-провайдере */
export interface ProviderInfo {
  name: string;
  model: string;
  available: boolean;
}

/** Конфигурация приложения (состояние) */
export interface AppState {
  // Текущая генерация
  currentGeneration: GenerationStatus | null;
  // Активен ли polling
  isPolling: boolean;
  // История документов
  history: DocumentInfo[];
  // Доступные провайдеры
  providers: ProviderInfo[];
  // Глобальная ошибка (не связанная с конкретной генерацией)
  globalError: string | null;
  // Флаг начальной загрузки
  isLoading: boolean;
}

/** Человекочитаемые названия этапов */
export const STAGE_LABELS: Record<GenerationStage, string> = {
  accepted: 'Принят в обработку',
  planning: 'Составление плана',
  annotating: 'Аннотирование разделов',
  generating: 'Генерация разделов',
  auditing: 'Аудит связности',
  assembling: 'Сборка документа',
  completed: 'Готово',
  failed: 'Ошибка',
};

/** Цвета этапов для progress bar / label */
export const STAGE_COLORS: Record<GenerationStage, string> = {
  accepted: '#6b7280',     // gray
  planning: '#3b82f6',     // blue
  annotating: '#8b5cf6',   // purple
  generating: '#f59e0b',   // amber
  auditing: '#ef4444',     // red
  assembling: '#10b981',   // green
  completed: '#10b981',    // green
  failed: '#ef4444',       // red
};
```

---

## 4. Components

### 4.1 GeneratorForm

**Назначение:** Форма ввода темы и выбора провайдера + кнопки запуска.

**Props:** нет (использует контекст/пропсы от App)

**State (локальный):**
| Поле | Тип | Начальное | Описание |
|------|-----|-----------|----------|
| `topic` | string | `""` | Тема регламента |
| `provider` | string | `"auto"` | Выбранный провайдер |
| `isGenerating` | boolean | `false` | Идёт ли генерация сейчас |
| `validationError` | string | `""` | Текст ошибки валидации |

**Props от родителя (входные):**
| Проп | Тип | Описание |
|------|-----|----------|
| `providers` | `ProviderInfo[]` | Список провайдеров для селекта |
| `disabled` | boolean | Блокировка формы (пока идёт генерация) |
| `onStartGeneration` | `(topic: string, provider: string, isMulti: boolean) => Promise<void>` | Колбэк запуска |
| `onCancelGeneration` | `() => void` | Колбэк отмены (остановка polling, сброс) |

**UI elements:**
1. **Text input** — topic, placeholder: "Введите тему регламента (например, Регламент по учёту ГСМ)", required
2. **Provider selector** — `<select>` из `providers`, по умолчанию `"auto"`
   - Отображать `(недоступен)` для провайдеров с `available: false`
   - Провайдер `"generation"` показывать как `"Многоэтапная (рекомендуется)"`
3. **Кнопка "Generate (single-stage)"** — запускает синхронную генерацию (legacy)
4. **Кнопка "Generate multi-stage (recommended)"** — запускает multi-stage
   - Стиль: primary (выделенная)
   - Подпись под кнопкой: "Рекомендуется для сложных регламентов"

**Валидация:**
- `topic.trim() === ""` → обе кнопки disabled
- `topic.length > 2000` → показать ошибку "Тема слишком длинная (макс. 2000 символов)"
- Если провайдер недоступен — disabled для соответствующего режима

**Поведение при генерации:**
- `isGenerating = true` → оба поля и обе кнопки disabled
- Показать spinner или текст "Генерация..."
- Кнопка "Cancel" вместо кнопок генерации
- После завершения (или ошибки) → `isGenerating = false`, форма разблокирована

---

### 4.2 ProgressPanel (NEW)

**Назначение:** Отображение прогресса multi-stage генерации. Появляется вместо ResultPanel во время генерации.

**Props:**
| Проп | Тип | Описание |
|------|-----|----------|
| `status` | `GenerationStatus` | Текущий статус |
| `elapsedSeconds` | number | Прошедшее время с момента старта |
| `onCancel` | `() => void` | Отмена генерации / возврат к форме |
| `onRetry` | `() => void` | Повтор (если failed) |

**UI layout:**
```
┌─────────────────────────────────────┐
│  ⏳ Генерация регламента             │
│  ─────────────────────────────────   │
│                                     │
│  [=============       ]  60%        │
│  Генерация разделов                  │
│  Раздел 5 из 10 (50%)               │
│                                     │
│  ⏱ Прошло: 2 мин 15 сек            │
│  ⏱ Осталось: ~3 мин                │
│                                     │
│  ┌─ Этапы ───────────────────────┐  │
│  │ ✅ План                        │  │
│  │ ✅ Аннотации                   │  │
│  │ ⏳ Генерация разделов (5/10)   │  │
│  │ ⬜ Аудит                       │  │
│  │ ⬜ Сборка                      │  │
│  └────────────────────────────────┘  │
│                                     │
│  [✕ Cancel]                         │
└─────────────────────────────────────┘
```

**Детали:**
- **Progress bar:** `width: ${status.stage_progress}%`, цвет динамический (STAGE_COLORS)
- **Текущий этап:** `status.current_stage` или `STAGE_LABELS[status.status]`
- **Section counter:** `status.completed_sections` / `status.total_sections`
- **Elapsed timer:** считать от `status.created_at` до now, обновлять каждую секунду (локальный `setInterval`)
- **Spinner:** анимация вращения рядом с заголовком во время генерации
- **Список этапов:** визуальный чеклист:
  - ✅ — завершённые этапы
  - ⏳ — текущий (с выделением)
  - ⬜ — предстоящие
- **Кнопка Cancel:** возвращает к форме, останавливает polling
- **Состояние failed:** progress bar красный, показать `error_message`, кнопка "Retry"

**Определение завершённых этапов по `status.status`:**
```
accepted      → всё ⬜
planning      → ✅ accepted, ⏳ planning, остальные ⬜
annotating    → ✅ accepted, ✅ planning, ⏳ annotating, остальные ⬜
generating    → ✅ accepted, ✅ planning, ✅ annotating, ⏳ generating, остальные ⬜
auditing      → ✅ accepted..generating, ⏳ auditing, ⬜ assembling
assembling    → ✅ accepted..auditing, ⏳ assembling, ⬜ completed
completed     → все ✅
failed        → все до failed — ✅/⏳, после — ❌
```

---

### 4.3 ResultPanel (обновлённый)

**Назначение:** Показывается, когда генерация завершена (status === "completed").

**Props:**
| Проп | Тип | Описание |
|------|-----|----------|
| `status` | `GenerationStatus` | Финальный статус (completed) |
| `onGenerateNew` | `() => void` | Сброс к форме для новой генерации |

**UI layout:**
```
┌─────────────────────────────────────┐
│  ✅ Регламент успешно создан!       │
│  ─────────────────────────────────   │
│                                     │
│  📄 Тема: Регламент учёта ГСМ      │
│  ⚙ Провайдер: Многоэтапная         │
│  📊 Разделов: 10                    │
│  ⏱ Время: 12 мин 30 сек            │
│                                     │
│  [⬇ Скачать .docx]                  │
│                                     │
│  [➕ Создать ещё регламент]         │
└─────────────────────────────────────┘
```

**Детали:**
- Кнопка "Download": `<a href={getDocumentDownloadUrl(status.document_id!)} download>` — прямая ссылка
- Если `document_id` отсутствует (статус completed, но нет ID) — показать ошибку
- Кнопка "Create new" → сброс: `currentGeneration = null`, форма очищается
- Время генерации: вычислить из `created_at` → `completed_at`

---

### 4.4 HistoryList (обновлённый)

**Назначение:** Список последних 20 документов.

**Props:**
| Проп | Тип | Описание |
|------|-----|----------|
| `documents` | `DocumentInfo[]` | Список документов |
| `onRefresh` | `() => void` | Принудительное обновление списка |

**UI layout (строка таблицы):**
```
┌──────┬────────────────┬────────────┬──────────────┬──────────┐
│  #   │ Тема           │ Провайдер  │ Дата         │ Действие │
├──────┼────────────────┼────────────┼──────────────┼──────────┤
│  1   │ Регламент...   │ generation │ 04.07.2026   │ [⬇]      │
│  2   │ Инструкция...  │ ollama     │ 03.07.2026   │ [⬇]      │
│  3   │ Порядок...     │ generation │ 02.07.2026   │ [⬇]      │
└──────┴────────────────┴────────────┴──────────────┴──────────┘
```

**Детали:**
- **Тема:** обрезать до 50 символов + "..."
- **Провайдер:** отображать `"generation"` как `"Многоэтапная"`, `"ollama"` как `"Ollama"`, и т.д.
- **Дата:** форматировать `created_at` в `DD.MM.YYYY HH:mm`
- **Действие:** кнопка "Download" (иконка ⬇), ссылка на `/api/documents/{id}/download`
- **Первый элемент:** выделять (если это только что завершённая генерация)
- **Badge (опционально):** для multi-stage генераций показывать бейдж `"multi-stage"` / `"single"`

**Пустое состояние:**
```
┌─────────────────────────────────────┐
│  📋 История генераций                │
│                                     │
│  Пока нет созданных регламентов.     │
│  Создайте первый регламент выше.     │
└─────────────────────────────────────┘
```

**Автообновление:**
- После завершения генерации → `onRefresh()` (перезапросить список)
- При каждом появлении компонента на экране (если список пустой)

---

## 5. API Client (api/client.ts)

```typescript
// ============================================================
// API Client — все вызовы к backend
// ============================================================

const API_BASE = '/api';

/**
 * Запуск multi-stage генерации.
 * POST /api/generate/multi
 */
export async function startGeneration(
  topic: string,
  provider?: string
): Promise<{ generation_id: string }> {
  const res = await fetch(`${API_BASE}/generate/multi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, provider: provider ?? 'auto' }),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody?.detail || await res.text());
  }

  return res.json(); // { generation_id, status, estimated_seconds }
}

/**
 * Получение статуса генерации.
 * GET /api/generate/{id}/status
 */
export async function getGenerationStatus(
  id: string
): Promise<GenerationStatus> {
  const res = await fetch(`${API_BASE}/generate/${id}/status`);

  if (res.status === 404) {
    throw new ApiError(404, 'Generation session not found');
  }
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  return res.json();
}

/**
 * Получение URL для скачивания документа.
 * GET /api/documents/{id}/download
 */
export function getDocumentDownloadUrl(documentId: string): string {
  return `${API_BASE}/documents/${documentId}/download`;
}

/**
 * Список документов (история, до 20 шт).
 * GET /api/documents
 */
export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json();
}

/**
 * Список доступных провайдеров.
 * GET /api/providers
 */
export async function listProviders(): Promise<ProviderInfo[]> {
  const res = await fetch(`${API_BASE}/providers`);
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json();
}

/**
 * Polling статуса генерации.
 *
 * - Опрашивает /api/generate/{id}/status каждые intervalMs
 * - Вызывает onProgress на каждый успешный ответ
 * - Завершается, когда status === 'completed' или status === 'failed'
 * - При ошибке сети — повторяет попытку (не прерывает polling)
 *
 * @param signal — AbortSignal для отмены (cleanup при размонтировании)
 */
export async function pollGenerationStatus(
  generationId: string,
  onProgress: (status: GenerationStatus) => void,
  signal?: AbortSignal,
  intervalMs: number = 3000,
): Promise<GenerationStatus> {
  // Флаг для проверки, не отменён ли polling
  let cancelled = false;

  if (signal) {
    signal.addEventListener('abort', () => { cancelled = true; }, { once: true });
  }

  const poll = async (): Promise<GenerationStatus> => {
    if (cancelled) {
      throw new DOMException('Polling cancelled', 'AbortError');
    }

    try {
      const status = await getGenerationStatus(generationId);

      if (cancelled) return null!; // будет перехвачено

      onProgress(status);

      if (status.status === 'completed' || status.status === 'failed') {
        return status;
      }

      // Продолжить polling
      await new Promise(resolve => setTimeout(resolve, intervalMs));
      return poll();
    } catch (err) {
      // Если отмена — не рекурсировать
      if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) {
        throw err;
      }

      // Сетевая ошибка — подождать и повторить
      console.warn('Polling error, retrying in 5s:', err);
      await new Promise(resolve => setTimeout(resolve, 5000));
      return poll();
    }
  };

  return poll();
}

// ============================================================
// Error class
// ============================================================
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(`API Error ${status}: ${message}`);
    this.name = 'ApiError';
  }
}
```

---

## 6. App.tsx — State Management

**Центральное состояние (useState / useReducer в App.tsx):**

```typescript
function App() {
  // --- Состояние ---
  const [currentGeneration, setCurrentGeneration] = useState<GenerationStatus | null>(null);
  const [history, setHistory] = useState<DocumentInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // --- Эффекты ---

  // Загрузка начальных данных
  useEffect(() => {
    Promise.all([listDocuments(), listProviders()])
      .then(([docs, provs]) => {
        setHistory(docs);
        setProviders(provs);
      })
      .catch(err => console.error('Initial load failed:', err))
      .finally(() => setIsInitialLoading(false));
  }, []);

  // --- Обработчики ---

  // Запуск генерации
  const handleStartGeneration = async (topic: string, provider: string, isMulti: boolean) => {
    // Устанавливаем placeholder-статус (accepted)
    setCurrentGeneration({
      id: 'pending',
      topic,
      status: 'accepted',
      current_stage: 'Принят в обработку',
      stage_progress: 0,
      total_sections: 0,
      completed_sections: 0,
      provider_used: provider,
      created_at: new Date().toISOString(),
    });
    setIsPolling(true);

    try {
      // Если multi-stage
      if (isMulti) {
        const { generation_id } = await startGeneration(topic, provider);

        // Запускаем polling (передаём AbortController)
        const abortController = new AbortController();
        // Сохраняем controller для возможности отмены

        const finalStatus = await pollGenerationStatus(
          generation_id,
          (status) => setCurrentGeneration(prev => ({
            ...prev!,
            ...status,
            id: generation_id,
            topic,
          })),
          abortController.signal,
          3000,
        );

        setCurrentGeneration(prev => ({
          ...prev!,
          ...finalStatus,
          id: generation_id,
          topic,
        }));

        // Обновляем историю
        const docs = await listDocuments();
        setHistory(docs);
      } else {
        // Single-stage: синхронный вызов POST /api/generate
        // (остаётся как legacy, без polling)
        // ...
      }
    } catch (err) {
      setCurrentGeneration(prev => prev ? {
        ...prev,
        status: 'failed',
        error_message: err instanceof Error ? err.message : 'Unknown error',
      } : null);
    } finally {
      setIsPolling(false);
    }
  };

  // Сброс (новая генерация)
  const handleGenerateNew = () => {
    setCurrentGeneration(null);
    setIsPolling(false);
  };

  // Рендер
  return (
    <div className="app">
      <header>
        <h1>📋 Генератор корпоративных регламентов</h1>
      </header>

      <main>
        <GeneratorForm
          providers={providers}
          disabled={isPolling}
          onStartGeneration={handleStartGeneration}
          onCancelGeneration={handleGenerateNew}
        />

        {/* Показываем ProgressPanel или ResultPanel в зависимости от статуса */}
        {currentGeneration && currentGeneration.status !== 'completed' && (
          <ProgressPanel
            status={currentGeneration}
            onCancel={handleGenerateNew}
            onRetry={() => handleStartGeneration(
              currentGeneration.topic,
              currentGeneration.provider_used || 'auto',
              true,
            )}
          />
        )}

        {currentGeneration?.status === 'completed' && (
          <ResultPanel
            status={currentGeneration}
            onGenerateNew={handleGenerateNew}
          />
        )}

        <HistoryList
          documents={history}
          onRefresh={() => listDocuments().then(setHistory)}
        />
      </main>
    </div>
  );
}
```

**Важные моменты:**
- `currentGeneration` — `null` когда нет активной генерации, иначе объект `GenerationStatus`
- polling запускается только для multi-stage
- После завершения генерации — автоматическое обновление `history`
- AbortController используется для отмены polling при размонтировании компонента или ручной отмене

---

## 7. User Flow

### Flow A: Multi-stage генерация (основной)

```
1. Страница загружается
   ├── GET /api/providers
   ├── GET /api/documents
   ├── Показать: GeneratorForm, HistoryList
   └── Поле topic пустое, кнопки disabled

2. Пользователь вводит тему "Регламент по учёту ГСМ"
   ├── Кнопки становятся активными (topic не пуст)
   └── Провайдер по умолчанию "auto"

3. Пользователь нажимает "Generate multi-stage (recommended)"
   ├── POST /api/generate/multi
   │   ├── body: { topic: "Регламент по учёту ГСМ", provider: "auto" }
   │   └── response: 202 { generation_id: "...", status: "accepted" }
   ├── GeneratorForm: disabled, показать Cancel
   ├── ProgressPanel: появляется
   │   ├── status: "accepted", progress: 0%
   │   └── Timer starts

4. Polling: GET /api/generate/{id}/status каждые 3 секунды
   ├── Poll 1: status: "planning", progress: 10%
   ├── Poll 2: status: "annotating", progress: 20%
   ├── Poll 3–12: status: "generating", progress: 30–70%
   │   ├── progress bar растёт
   │   └── section counter: 3/10, 5/10, 8/10...
   ├── Poll 13: status: "auditing", progress: 80%
   ├── Poll 14: status: "assembling", progress: 95%
   └── Poll 15: status: "completed", progress: 100%, document_id: "..."

5. ResultPanel появляется
   ├── Успешное сообщение
   ├── Кнопка "Download" → GET /api/documents/{id}/download → .docx
   └── Кнопка "Create new" → сброс состояния

6. HistoryList обновлён
   └── Новый документ — первый в списке
```

### Flow B: Отмена генерации

```
1–3. Как в Flow A
4. Пользователь нажимает Cancel в ProgressPanel
   ├── AbortController.abort() → polling остановлен
   ├── setCurrentGeneration(null)
   └── GeneratorForm разблокирован
```

### Flow C: Ошибка генерации

```
1–3. Как в Flow A
4. Poll N: status: "failed", error_message: "Провайдер Ollama недоступен"
   ├── ProgressPanel: красный progress bar, текст ошибки
   ├── Кнопка "Retry" → перезапуск с той же темой
   └── Кнопка "Cancel" → возврат к форме
```

### Flow D: Single-stage (legacy)

```
1–2. Как в Flow A
3. Пользователь выбирает provider: "ollama", нажимает "Generate"
   ├── POST /api/generate (синхронный)
   ├── Спиннер на кнопке (ожидание ответа)
   ├── Response: 201 { document_id, ... }
   └── ResultPanel: успех, кнопка Download
```

---

## 8. Files to Create / Modify

### 8.1. Новые / изменённые файлы

| # | Файл | Действие | Назначение |
|---|------|----------|-----------|
| F1 | `frontend/package.json` | ✅ Создать | Зависимости (react, react-dom, typescript, vite, @vitejs/plugin-react) |
| F2 | `frontend/tsconfig.json` | ✅ Создать | TypeScript конфиг |
| F3 | `frontend/tsconfig.node.json` | ✅ Создать | TS config для Vite |
| F4 | `frontend/vite.config.ts` | ✅ Создать | Vite + proxy `/api` → `http://localhost:8000` |
| F5 | `frontend/index.html` | ✅ Создать | HTML entry point |
| F6 | `frontend/src/main.tsx` | ✅ Создать | React entry point |
| F7 | `frontend/src/App.tsx` | ✅ Создать (или изменить) | Главный компонент, состояние, роутинг |
| F8 | `frontend/src/App.css` | ✅ Создать | Стили (min-width 320px, адаптивность) |
| F9 | `frontend/src/types.ts` | ✅ Создать | TypeScript интерфейсы (см. раздел 3) |
| F10 | `frontend/src/api/client.ts` | ✅ Создать | API клиент (см. раздел 5) |
| F11 | `frontend/src/components/GeneratorForm.tsx` | ✅ Создать (или изменить) | Форма ввода темы, выбора провайдера, кнопки |
| F12 | `frontend/src/components/ProgressPanel.tsx` | ✅ **НОВЫЙ** | Индикатор прогресса multi-stage |
| F13 | `frontend/src/components/ResultPanel.tsx` | ✅ Создать (или изменить) | Результат генерации (успех/ошибка) |
| F14 | `frontend/src/components/HistoryList.tsx` | ✅ Создать (или изменить) | История последних 20 генераций |
| F15 | `frontend/public/favicon.svg` | ✅ Создать | Иконка |

### 8.2. Структура директории frontend

```
frontend/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── App.css
    ├── types.ts
    ├── api/
    │   └── client.ts
    └── components/
        ├── GeneratorForm.tsx
        ├── ProgressPanel.tsx       // NEW
        ├── ResultPanel.tsx
        └── HistoryList.tsx
```

---

## 9. Acceptance Criteria (AC)

| # | Критерий | Как проверить |
|---|----------|---------------|
| AC-01 | Пользователь может ввести тему, выбрать провайдера (default "auto") | Ввести текст, проверить select |
| AC-02 | Кнопки генерации disabled при пустой теме | Не вводить текст → обе кнопки disabled |
| AC-03 | Нажатие "Generate multi-stage" → POST /api/generate/multi → 202 | DevTools Network |
| AC-04 | После 202 появляется ProgressPanel с progress bar | Визуально |
| AC-05 | Progress bar обновляется каждые 3 секунды (polling) | DevTools Network: GET /api/generate/{id}/status каждые ~3s |
| AC-06 | ProgressPanel показывает название текущего этапа | Проверить текст статуса |
| AC-07 | ProgressPanel показывает счётчик разделов (3/10) | Проверить при этапе generating |
| AC-08 | ProgressPanel показывает прошедшее время | Сверить с секундомером |
| AC-09 | ProgressPanel показывает список этапов с отметками (✅⏳⬜) | Визуально |
| AC-10 | После status === "completed" → ProgressPanel заменяется на ResultPanel | Визуально |
| AC-11 | ResultPanel: тема, провайдер, количество разделов, время генерации | Проверить текст |
| AC-12 | ResultPanel: кнопка "Download" → скачивается .docx | Клик, проверить файл |
| AC-13 | ResultPanel: кнопка "Create new" → сброс к форме | Клик, форма пуста |
| AC-14 | При status === "failed" → красный progress bar + сообщение об ошибке + Retry | Имитировать ошибку backend |
| AC-15 | Cancel → polling остановлен, форма разблокирована | DevTools: нет запросов после cancel |
| AC-16 | HistoryList показывает 20 последних документов (тема, провайдер, дата, download) | Проверить список |
| AC-17 | После завершения генерации HistoryList обновляется | Проверить первый элемент |
| AC-18 | HistoryList: topic обрезан до 50 символов | Создать документ с длинной темой |
| AC-19 | Скачанный .docx открывается и читается | Открыть в Word/LibreOffice |
| AC-20 | Страница адаптивна (min-width 320px) | DevTools: responsive mode 320px |
| AC-21 | Обработка ошибок: уведомление при 422 / 503 / 500 | Имитировать ошибки через DevTools mock |
| AC-22 | Single-stage (legacy) кнопка "Generate" продолжает работать | POST /api/generate → 201 + download |
| AC-23 | Провайдер "generation" отображается отдельно с пометкой "рекомендуется" | Визуально в select |
| AC-24 | Недоступные провайдеры помечены "(недоступен)" | Визуально в select |

---

## 10. Out of Scope (что НЕ входит в Stage 3 v2)

| № | Что не входит | Причина |
|---|---------------|---------|
| 1 | Авторизация / регистрация | Нет требований |
| 2 | Темы оформления (только минимальный CSS) | MVP |
| 3 | E2E-тесты | Stage 5+ |
| 4 | Развёртывание (Docker, деплой) | Stage 5+ |
| 5 | WebSocket для прогресса | MVP — polling достаточно |
| 6 | Возможность прервать генерацию на backend (DELETE) | Нет в MVP |
| 7 | Возобновление (resume) после падения | Нет в MVP |
| 8 | Email-уведомление о готовности | Stage 5+ |
| 9 | Перегенерация отдельного раздела | Stage 5+ |
| 10 | История с пагинацией (>20 записей) | Stage 5+ |
| 11 | Unit-тесты фронтенда | Будут добавлены отдельно |

---

## 11. Edge Cases

| Ситуация | Ожидаемое поведение |
|----------|--------------------|
| **Пользователь закрыл вкладку во время генерации** | Polling прекращается. Backend продолжает генерацию. При повторном открытии — документ будет в истории |
| **Пользователь нажал Generate дважды** | Первая генерация отменяется (cancel polling), стартует новая |
| **Backend вернул 404 для generation_id** | Polling останавливается, ошибка "Сессия не найдена" |
| **Backend вернул 503 при старте** | Ошибка отображается в форме, генерация не начинается |
| **Backend вернул 422 (пустая тема)** | Показать ошибку валидации под полем ввода |
| **Polling: сетевой таймаут** | Повторить через 5 секунд (не останавливать polling) |
| **Polling: несколько последовательных таймаутов (>5)** | Показать предупреждение "Соединение нестабильно", продолжить polling |
| **document_id отсутствует при status=completed** | Показать "Ошибка: ID документа не получен", кнопка "Retry" |
| **total_sections = 0 (начальные этапы, до генерации плана)** | Показывать "..." или "—" вместо 0/0 |
| **Длинная тема (>100 символов) в ResultPanel** | Перенос строки, без обрезания |
| **Очень короткая тема (<5 символов)** | Валидация проходит (минимальная длина не ограничена), но качество документа может быть низким |

---

## 12. Risks and Mitigations

| № | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| R1 | **Polling создаёт нагрузку на backend** при множестве одновременных пользователей | Низкая | Среднее | Backend кеширует статус в памяти (или использует быстрый SQLite read). При необходимости — увеличить интервал до 5 секунд |
| R2 | **Пользователь уходит из-за долгой генерации** (>10 минут) | Средняя | Среднее | Показывать реалистичное оценочное время на старте. ProgressPanel удерживает внимание |
| R3 | **AbortController не поддерживается в старых браузерах** | Низкая | Низкое | В `tsconfig` target `es2017` — AbortController поддерживается везде, кроме IE11 |
| R4 | **Переполнение стека при рекурсивном polling** | Низкая | Низкое | `poll()` рекурсивна, но асинхронна — стек не растёт (каждый вызов ждёт setTimeout) |
| R5 | **Backend не поддерживает CORS для фронта** | Средняя | Высокое | `vite.config.ts` proxy перенаправляет `/api` → `localhost:8000` — CORS не нужен |

---

## 13. Vite Config (vite.config.ts)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 14. Implementation Notes for FE

### 14.1. Порядок реализации (рекомендуемый)

1. **Init:** `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `main.tsx` — скелет Vite + React
2. **Types:** `types.ts` — все интерфейсы
3. **API Client:** `api/client.ts` — все функции, включая `pollGenerationStatus`
4. **GeneratorForm:** форма с валидацией (можно тестировать без polling)
5. **ProgressPanel:** рендеринг на мок-данных (заглушка статуса)
6. **ResultPanel:** рендеринг готового результата
7. **HistoryList:** загрузка и отображение списка
8. **App.tsx:** сборка, состояние, интеграция polling

### 14.2. Ключевые решения

- **Polling** — рекурсивный `async` с `setTimeout` (не `setInterval`), чтобы избежать наложения запросов
- **Elapsed timer** — локальный `setInterval` в ProgressPanel (обновление каждую секунду)
- **Cancel** — через `AbortController`, без дополнительных запросов к backend
- **Стили** — минимальные, без CSS-фреймворков. Достаточно `App.css` с flexbox/grid
- **Стейт-менеджмент** — только `useState`/`useEffect` в App.tsx (без Redux/Zustand)

### 14.3. Зависимости package.json

```json
{
  "name": "srp-frontend",
  "private": true,
  "version": "0.3.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

---

## 15. Open Questions

| № | Вопрос | Варианты | Предложение SA |
|---|--------|----------|---------------|
| Q1 | **Отдельный endpoint `/api/generate/multi` или параметр `provider=generation`?** | 1) Новый endpoint; 2) Тот же endpoint с параметром | Решение за PM/BE. В этом spec — `/api/generate/multi` |
| Q2 | **Что показывать в elapsed time для multi-stage?** | 1) Время от старта генерации; 2) Время текущего этапа | От старта генерации (общее) |
| Q3 | **Нужна ли кнопка "Retry" при failed?** | 1) Да, с той же темой; 2) Нет, только "Create new" | Да, Retry — пользователь не хочет вводить тему заново |
| Q4 | **Как отображать провайдера "generation" в селекте?** | 1) Отдельный пункт; 2) Объединить с "auto" | Отдельный пункт "Многоэтапная (рекомендуется)" |
| Q5 | **Показывать ли Toast/уведомления при ошибках?** | 1) Да, всплывающее уведомление; 2) Нет, только в форме | Только в форме — MVP |

---

*Документ подготовлен: SA, 04.07.2026*
*Версия: 0.3.0 (Stage 3 v2)*
*Статус: готов к утверждению PM / реализации FE*
