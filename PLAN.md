# PLAN.md: Bookmark Processing Pipeline

## 1. Project Goal

The goal is to create a robust, parallelized pipeline in Python to process a list of ~6000 bookmarks. For each bookmark, the pipeline will perform a series of actions: check if the URL is live, lint its tags, summarize its content using an LLM, suggest new tags using an LLM, and finally save the processed data to a structured output format.

The pipeline must be idempotent and resumable to handle interruptions, especially when running in resource-constrained environments like GitHub Actions.

## 2. Core Technologies

The implementation will be in **Python 3.10+** and will leverage the following core libraries:

* **Workflow Orchestration:** `prefect` (version 2.x) - To define, orchestrate, and observe the workflow. Its declarative features for retries, caching, and concurrency are central to this plan.
* **HTTP Requests:** `httpx` - For performing synchronous and asynchronous HTTP HEAD/GET requests.
* **Headless Browser:** `playwright` - For the final fallback in the liveness check, capable of rendering JavaScript-heavy pages.
* **Data Validation:** `pydantic` - To define clear, type-hinted data models for inputs, outputs, and intermediate states.
* **Content Extraction:** `beautifulsoup4` with `lxml` - To parse HTML and extract the main textual content from a webpage before sending it to an LLM.
* **LLM Client:** `llm` - For interacting with local and remote Large Language Models via its Python API.

### 2.1. Development Tooling

*   **Dependency & Environment Management:** `uv` will be used for creating virtual environments and managing project dependencies.
*   **Linting & Formatting:** `ruff` will be used to enforce code style and quality.
*   **Testing Framework:** `pytest` will be used for writing and running tests. HTTP requests made with `httpx` will be mocked using the `respx` library, and LLM API calls will be mocked using `pytest-mock`.

### 2.2. Configuration

*   **Application Settings:** General application settings, such as the LLM model to use, will be stored in `pyproject.toml` under a `[tool.bookmark-processor]` table.
*   **Blessed Tags:** The canonical list of approved tags will be stored in a `blessed_tags.txt` file in the project root, with one tag per line.

## 3. Architectural Approach

The architecture is based on a **Stateful, Idempotent Worker** pattern, implemented using Prefect.

1.  **Top-Level Flow (`process_all_bookmarks_flow`):** This flow will orchestrate the entire process. It will read the list of all bookmarks and trigger a separate subflow for each one. It will use Prefect's `ConcurrentTaskRunner` to process multiple bookmarks in parallel.
2.  **Bookmark Subflow (`process_bookmark_flow`):** This flow represents the Directed Acyclic Graph (DAG) of operations for a *single* bookmark. It is responsible for calling the individual tasks in the correct order.
3.  **Liveness Check Subflow (`liveness_flow`):** To handle the complex, multi-stage liveness check, a dedicated subflow will be created. This encapsulates the "HEAD -> GET -> Headless" fallback logic, keeping the main bookmark flow clean.
4.  **Atomic Tasks (`@task`):** Each individual action (e.g., making a single HTTP request, calling an LLM) will be implemented as a distinct Prefect `@task`. This allows us to apply specific configurations for **retries, timeouts, and caching** to each action. Caching is critical for idempotency and efficiency on re-runs.

## 4. Data Models

We will use Pydantic models to ensure data consistency throughout the pipeline. The input and output format will be the same, using a single `Bookmark` model that mirrors the source JSON structure.

```python
# To be defined in models.py

from pydantic import BaseModel, field_validator
from typing import List, Optional, Literal

class Bookmark(BaseModel):
    href: str
    description: str
    extended: str
    meta: str
    hash: str
    time: str
    shared: str
    toread: str
    tags: List[str]

    @field_validator("tags", mode="before")
    @classmethod
    def split_tags(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return v.split()
        return v

class LivenessResult(BaseModel):
    status: Literal["success", "failed"]
    method: Optional[Literal["head_then_get", "get", "headless"]] = None
    final_url: Optional[str] = None
    content: Optional[str] = None # HTML content
    error_message: Optional[str] = None
```

## 5. Workflow Implementation Details

### 5.1. Top-Level Flow: `process_all_bookmarks_flow`

  * **Decorator:** `@flow(name="Process All Bookmarks", task_runner=ConcurrentTaskRunner())`
  * **Input:** `bookmarks_filepath: str`, `output_filepath: str`
  * **Logic:**
    1.  Read the bookmarks from the input JSON file into a list of `Bookmark` models.
    2.  Submit a `process_bookmark_flow` run for each bookmark, collecting the future results.
    3.  Gather the results (the modified `Bookmark` objects) from all completed subflow runs.
    4.  Call `save_results(bookmarks, output_filepath)` to write all processed bookmarks to the output file.

### 5.2. Bookmark Subflow: `process_bookmark_flow`

  * **Decorator:** `@flow(name="Process Single Bookmark")`
  * **Input:** `bookmark: Bookmark`
  * **Output:** `Bookmark` (the modified bookmark)
  * **Logic:**
    1.  Call `lint_tags(bookmark.tags)` and log any warnings.
    2.  Call `liveness_flow(bookmark.href)`.
    3.  If `liveness_flow` fails (raises `LivenessCheckFailed`):
        *   Add `"not-live"` to `bookmark.tags` if not already present.
        *   Return the `bookmark`.
    4.  If `liveness_flow` succeeds, it returns a `LivenessResult`.
    5.  A text source is needed for the LLM. Use `bookmark.extended` if it's not empty, otherwise, call `extract_main_content(liveness_result.content)`.
    6.  If `bookmark.extended` was originally empty, call `summarize_content(text_source)` and update `bookmark.extended` with the result.
    7.  Call `suggest_tags(text_source)` and add any new tags to `bookmark.tags`.
    8.  Return the modified `bookmark`.

### 5.3. Liveness Subflow: `liveness_flow`

  * **Decorator:** `@flow(name="Check URL Liveness")`
  * **Input:** `url: str`
  * **Output:** `LivenessResult`
  * **Logic (Fallback Chain):**
    1.  **Try HEAD:**
          * `try`: Call `attempt_head_request(url)`. On success, call `attempt_get_request` with the final redirected URL to get content. Return a `LivenessResult` with `status="success"` and `method="head_then_get"`.
          * `except Exception`: Log the failure and proceed to the next step.
    2.  **Try GET:**
          * `try`: Call `attempt_get_request(url)`. On success, return a `LivenessResult` with `status="success"` and `method="get"`.
          * `except Exception`: Log the failure and proceed.
    3.  **Try Headless:**
          * `try`: Call `attempt_headless_browser(url)`. On success, return a `LivenessResult` with `status="success"` and `method="headless"`.
          * `except Exception`: Log the failure.
    4.  If all methods fail, `raise LivenessCheckFailed("...")` to signal total failure to the parent flow.

### 5.4. Individual Task Definitions (`@task`)

All tasks that perform network I/O or heavy computation should use caching.
`CACHE_SETTINGS = dict(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))`

  * **`attempt_head_request(url: str) -> str`**
      * Decorator: `@task(retries=2, retry_delay_seconds=5, **CACHE_SETTINGS)`
      * Action: Use `httpx` to make a `HEAD` request. Follow redirects. Return the final URL.
  * **`attempt_get_request(url: str) -> dict`**
      * Decorator: `@task(retries=2, retry_delay_seconds=10, **CACHE_SETTINGS)`
      * Action: Use `httpx` to make a `GET` request. Return a dict `{"final_url": str, "content": str}`.
  * **`attempt_headless_browser(url: str) -> dict`**
      * Decorator: `@task(retries=1, retry_delay_seconds=30, **CACHE_SETTINGS)`
      * Action: Use `playwright` to load the page. Return a dict `{"final_url": str, "content": str}`.
  * **`extract_main_content(html_content: str) -> str`**
      * Decorator: `@task(**CACHE_SETTINGS)`
      * Action: Use `BeautifulSoup` to parse HTML and implement logic to extract the core article text, stripping out boilerplate like navbars, ads, and footers.
  * **`lint_tags(tags: List[str]) -> List[str]`**
      * Decorator: `@task` (No caching needed, it's fast).
      * Action: Compare input tags against a "blessed" list read from `blessed_tags.txt`. Return a list of warnings for tags that are not in the list.
  * **`summarize_content(text: str) -> str`**
      * Decorator: `@task(**CACHE_SETTINGS)`
      * Action: Call the LLM API (via `llm` library) with the text to generate a summary.
  * **`suggest_tags(text: str) -> List[str]`**
      * Decorator: `@task(**CACHE_SETTINGS)`
      * Action: Call the LLM API (via `llm` library) to suggest relevant tags.
  * **`save_results(results: List[Bookmark], filepath: str)`**
      * Decorator: `@task`
      * Action: Write the list of processed `Bookmark` objects to the specified output JSON file, overwriting it if it exists.

## 6. Proposed Project Structure

```
/bookmark-processor/
|-- tests/              # Pytest test files
|-- main.py             # Main entrypoint, contains flow definitions
|-- models.py           # Pydantic data models
|-- tasks/
|   |-- __init__.py
|   |-- liveness.py     # Contains liveness-related tasks
|   |-- processing.py   # Contains content processing tasks (LLM, linting)
|   |-- io.py           # Contains save_results task
|-- bookmarks_input.json # Example input data
|-- blessed_tags.txt    # List of approved tags, one per line
|-- pyproject.toml      # Project dependencies and tool configuration
|-- prefect.yaml        # Prefect deployment configuration (optional)
```

## 7. Testing Strategy

*   **Unit Tests:** Each task will be tested in isolation. For example, `extract_main_content` will be tested with sample HTML strings, and `lint_tags` will be tested with various tag lists.
*   **Integration Tests:** The interaction between tasks within a flow will be tested. This will involve mocking external services. HTTP requests made with `httpx` will be mocked using the `respx` library, and LLM API calls will be mocked using `pytest-mock`.
*   **Flow Tests:** The `liveness_flow` and `process_bookmark_flow` will be tested as units, using Prefect's testing utilities to run them synchronously and assert their outcomes against mock data.

