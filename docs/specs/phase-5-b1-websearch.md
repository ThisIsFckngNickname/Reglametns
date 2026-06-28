# Phase 5 B1: WebSearchService Specification

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 5 / Инкремент B1 — WebSearchService (обязательный)
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Существующая реализация](#2-существующая-реализация)
3. [Изменения для B1](#3-изменения-для-b1)
   - 3.1 WebSearchService становится обязательным
   - 3.2 Парсинг содержимого страниц
   - 3.3 Метод enrich_prompt()
   - 3.4 Обработка ошибок
4. [Контракты](#4-контракты)
5. [Зависимости](#5-зависимости)
6. [Тестирование](#6-тестирование)

---

## 1. Контекст и цель

### 1.1 Текущая ситуация

`WebSearchService` уже реализован в `backend/app/services/web_search_service.py` и поддерживает:

- DuckDuckGo поиск (бесплатно, без API-ключа) — через библиотеку `duckduckgo_search`
- Tavily API (требуется API-ключ)
- SerpAPI (требуется API-ключ)

Сервис возвращает список результатов с полями: `title`, `snippet`, `url`.

### 1.2 Проблемы

1. **Только snippet** — возвращается только краткое описание (snippet), нет полного текста страницы. LLM не может извлечь конкретные нормы, номера статей, даты.
2. **Опциональность** — сервис выключается через `settings.web_search_enabled`. В B1 поиск должен быть **обязательным** шагом генерации.
3. **Нет форматирования** — нет метода для подготовки результатов к вставке в промпт.
4. **Нет извлечения контента** — даже если страница доступна, её текст не парсится.

### 1.3 Цель B1

- Сделать веб-поиск обязательным (не отключаемым через settings)
- Добавить парсинг содержимого топ-N страниц (через httpx + BeautifulSoup)
- Добавить метод `enrich_prompt()` для форматированного вывода
- Graceful degradation: при ошибке поиска или парсинга — пропустить блок, но не прерывать генерацию

---

## 2. Существующая реализация

### 2.1 Текущий код

```python
class WebSearchService:
    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the web for information on a topic.
        
        Returns:
            List of dicts with 'title', 'snippet', 'url'.
        """
        if not settings.web_search_enabled:
            return []
        
        provider = settings.web_search_provider
        if provider == "duckduckgo":
            return await self._search_duckduckgo(query, max_results)
        # ...tavily, serpapi...
```

**Проблема:** `settings.web_search_enabled` может быть `False`, что отключает весь поиск.

### 2.2 Текущий вызов в GeneratorService

```python
# В GeneratorService.generate():
web_results = []
if settings.web_search_enabled:
    try:
        web_results = await web_search_service.search(context_description)
    except Exception as e:
        logger.warning(f"Web search failed (will continue without): {e}")
```

---

## 3. Изменения для B1

### 3.1 WebSearchService становится обязательным

**Изменение в `config.py`:**

```python
# Было:
web_search_enabled: bool = True

# Стало:
web_search_enabled: bool = True  # deprecated — всегда True для B1
# Сервис всегда включён; для тестов/демо можно принудительно отключить
```

**Изменение в `generator_service.py`:**

```python
# Было:
if settings.web_search_enabled:
    web_results = await web_search_service.search(...)

# Стало (V2):
# Всегда выполняем поиск; если отключено в config — пропускаем с логом
web_results_text = None
try:
    web_results_text = await web_search_service.enrich_prompt(topic)
except Exception as e:
    logger.warning(f"Web search failed (will continue without): {e}")
    # Не прерываем генерацию
```

**settings.web_search_enabled** остаётся в конфиге как флаг для тестовых сред (чтобы не делать реальные запросы в unit-тестах). В production — всегда `True`.

### 3.2 Парсинг содержимого страниц

Новый метод `_fetch_page_content()`:

```python
async def _fetch_page_content(self, url: str, timeout: int = 10) -> str | None:
    """Fetch and extract text content from a webpage.
    
    Uses httpx to fetch the page, then BeautifulSoup to extract
    readable text content.
    
    Args:
        url: Page URL to fetch.
        timeout: Request timeout in seconds.
    
    Returns:
        Extracted text content, or None if failed.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "footer", "header", 
                           "aside", "noscript", "iframe", "form"]):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator="\n", strip=True)
            
            # Clean up: collapse multiple newlines, limit length
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)
            
            # Limit to 5000 chars per page
            if len(text) > 5000:
                text = text[:5000] + "\n\n[...]"
            
            return text
            
    except Exception as e:
        logger.warning(f"Failed to fetch page content {url}: {e}")
        return None
```

**Требования к зависимостям (pyproject.toml / requirements.txt):**

```
beautifulsoup4>=4.12.0
lxml>=5.0.0
httpx>=0.27.0
```

### 3.3 Метод enrich_prompt()

Новый метод, который объединяет поиск + парсинг + форматирование:

```python
async def enrich_prompt(self, topic: str, max_results: int = 5) -> str | None:
    """Search the web and format results for LLM prompt.
    
    Pipeline:
    1. Search DuckDuckGo for the topic
    2. Pick top 3 results
    3. Fetch full page content for each
    4. Format as structured text
    
    Args:
        topic: Document topic to search for.
        max_results: Max search results (default 5).
    
    Returns:
        Formatted text for prompt insertion, or None if search failed.
    """
    # 1. Search
    results = await self.search(topic, max_results)
    if not results:
        return None
    
    # 2. Pick top 3 for content extraction
    top_results = results[:3]
    
    # 3. Fetch content for each
    formatted_lines = []
    for i, result in enumerate(top_results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        
        # Try to fetch full page content
        content = await self._fetch_page_content(url)
        
        formatted_lines.append(f"Источник {i}: {title}")
        if content:
            # Use full content if available
            formatted_lines.append(f"    {content[:1000]}")
        else:
            # Fallback to snippet
            formatted_lines.append(f"    {snippet[:500]}")
        formatted_lines.append(f"    URL: {url}")
        formatted_lines.append("")  # empty line between sources
    
    return "\n".join(formatted_lines)
```

### 3.4 Обработка ошибок

| Сценарий | Поведение |
|----------|-----------|
| DuckDuckGo rate limit (HTTP 429) | Логировать warning, вернуть None |
| Страница не загружается (timeout, 404, 500) | Использовать snippet как fallback |
| BeautifulSoup parser error | Вернуть сырой текст (без парсинга) |
| Все 3 страницы не загрузились | Использовать snippet из результатов поиска |
| Поиск вернул 0 результатов | Вернуть None |
| Нет сети / DNS error | Логировать error, вернуть None |

```python
# Пример: enrich_prompt с fallback
async def enrich_prompt(self, topic: str, max_results: int = 5) -> str | None:
    try:
        results = await self.search(topic, max_results)
        if not results:
            logger.info(f"No web search results for: {topic[:50]}")
            return None
        
        formatted = []
        for i, r in enumerate(results[:3], 1):
            title = r.get("title", "")
            url = r.get("url", "")
            snippet = r.get("snippet", "")
            
            content = await self._fetch_page_content(url)
            
            formatted.append(f"Источник {i}: {title}")
            if content:
                formatted.append(f"    {content[:1000]}")
            else:
                formatted.append(f"    {snippet[:500]}")
            formatted.append(f"    URL: {url}")
        
        result_text = "\n".join(formatted)
        logger.info(
            f"Web search enrich_prompt: {len(results)} results, "
            f"{len(result_text)} chars for: {topic[:50]}"
        )
        return result_text
        
    except Exception as e:
        logger.error(f"Web search enrich_prompt failed: {e}", exc_info=True)
        return None  # Never block generation
```

---

## 4. Контракты

### 4.1 WebSearchService (расширенный)

```python
class WebSearchService:
    """Service for searching the web and enriching prompts."""
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the web for information on a topic.
        
        Returns list of dicts with 'title', 'snippet', 'url'.
        Returns empty list on error (never raises).
        """
        ...
    
    async def enrich_prompt(
        self,
        topic: str,
        max_results: int = 5,
    ) -> str | None:
        """Search web and format results as structured text for prompts.
        
        Args:
            topic: Document topic to search for.
            max_results: Max raw search results to fetch.
        
        Returns:
            Formatted multi-line string ready for prompt insertion,
            or None if search completely failed.
        """
        ...
    
    async def _fetch_page_content(
        self,
        url: str,
        timeout: int = 10,
    ) -> str | None:
        """Fetch and extract readable text from a webpage.
        
        Uses httpx + BeautifulSoup. Never raises — returns None on error.
        Returns up to 5000 chars of extracted text.
        """
        ...
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        """DuckDuckGo search implementation (exists, minor updates)."""
        ...
```

### 4.2 Изменения в config.py

```python
# B1: no changes needed to settings structure, but semantics change:
# web_search_enabled = True is now the default and should remain True in production.
# False is allowed for tests/offline demo only.
```

### 4.3 Изменения в GeneratorService

```python
# В методе generate_document() (V2):
web_results_text = None
try:
    web_results_text = await web_search_service.enrich_prompt(topic)
    if web_results_text:
        logger.info(f"Web search enrich returned {len(web_results_text)} chars")
    else:
        logger.info("Web search enrich returned no results")
except Exception as e:
    logger.warning(f"Web search failed (will continue without): {e}")

# web_results_text передаётся в PromptBuilder V2, который
# вставляет его в секцию "ИНФОРМАЦИЯ ИЗ ИНТЕРНЕТА" или
# "[РЕЗУЛЬТАТЫ ПОИСКА В ИНТЕРНЕТЕ]"
```

---

## 5. Зависимости

### 5.1 Python-пакеты

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `duckduckgo_search` | >=4.0.0 | Поиск через DuckDuckGo (уже есть) |
| `httpx` | >=0.27.0 | HTTP-запросы для парсинга страниц (уже есть) |
| `beautifulsoup4` | >=4.12.0 | Парсинг HTML (новый) |
| `lxml` | >=5.0.0 | HTML-парсер для BeautifulSoup (новый) |

### 5.2 Добавить в `requirements.txt`

```
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

---

## 6. Тестирование

### 6.1 Unit-тесты

```python
# test_web_search_service.py

async def test_enrich_prompt_empty_topic():
    """Пустая тема не должна вызывать ошибку."""
    result = await web_search_service.enrich_prompt("")
    assert result is None

async def test_enrich_prompt_handles_network_error():
    """При ошибке сети enrich_prompt возвращает None, не raise."""
    # Мокаем HTTP клиент
    with patch("httpx.AsyncClient.get", side_effect=Exception("No network")):
        result = await web_search_service.enrich_prompt("test topic")
        assert result is None

async def test_fetch_page_content_timeout():
    """Таймаут при загрузке страницы не вызывает ошибку."""
    with patch("httpx.AsyncClient.get", side_effect=TimeoutException("Timeout")):
        content = await web_search_service._fetch_page_content("https://example.com")
        assert content is None

async def test_fetch_page_content_returns_text():
    """Успешная загрузка страницы возвращает текст."""
    # Используем тестовый HTML
    mock_html = "<html><body><p>Test content</p></body></html>"
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        content = await web_search_service._fetch_page_content("https://example.com")
        assert content is not None
        assert "Test content" in content

async def test_ddg_search_returns_results():
    """DuckDuckGo возвращает результаты в правильном формате."""
    results = await web_search_service._search_duckduckgo("test query", max_results=3)
    if results:  # Может не быть сети в CI
        assert len(results) <= 3
        for r in results:
            assert "title" in r
            assert "snippet" in r
            assert "url" in r
```

### 6.2 Интеграционные тесты

```python
# test_generator_v2.py

async def test_generation_with_web_search():
    """Генерация с включённым веб-поиском."""
    # Мокаем WebSearchService.enrich_prompt
    with patch.object(web_search_service, "enrich_prompt", return_value="Test web content"):
        result = await generator_service.generate_document(
            topic="Test topic",
            company_id=1,
            document_type="regulation",
        )
        assert result is not None
        assert result.status == "draft"

async def test_generation_with_failed_web_search():
    """Генерация НЕ блокируется при ошибке веб-поиска."""
    with patch.object(web_search_service, "enrich_prompt", side_effect=Exception("Fail")):
        result = await generator_service.generate_document(
            topic="Test topic",
            company_id=1,
            document_type="regulation",
        )
        assert result is not None  # Генерация продолжается
```
