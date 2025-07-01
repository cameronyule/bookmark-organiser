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
* **LLM Client:** A placeholder for a specific client library (e.g., `openai`, `anthropic`). The implementation should abstract this into a dedicated task.

### 2.1. Development Tooling

*   **Dependency & Environment Management:** `uv` will be used for creating virtual environments and managing project dependencies.
*   **Linting & Formatting:** `ruff` will be used to enforce code style and quality.
*   **Testing Framework:** `pytest` will be used for writing and running tests. HTTP requests made with `httpx` will be mocked using the `respx` library, and LLM API calls will be mocked using `pytest-mock`.

## 3. Architectural Approach

The architecture is based on a **Stateful, Idempotent Worker** pattern, implemented using Prefect.

1.  **Top-Level Flow (`process_all_bookmarks_flow`):** This flow will orchestrate the entire process. It will read the list of all bookmarks and trigger a separate subflow for each one. It will use Prefect's `ConcurrentTaskRunner` to process multiple bookmarks in parallel.
2.  **Bookmark Subflow (`process_bookmark_flow`):** This flow represents the Directed Acyclic Graph (DAG) of operations for a *single* bookmark. It is responsible for calling the individual tasks in the correct order.
3.  **Liveness Check Subflow (`liveness_flow`):** To handle the complex, multi-stage liveness check, a dedicated subflow will be created. This encapsulates the "HEAD -> GET -> Headless" fallback logic, keeping the main bookmark flow clean.
4.  **Atomic Tasks (`@task`):** Each individual action (e.g., making a single HTTP request, calling an LLM) will be implemented as a distinct Prefect `@task`. This allows us to apply specific configurations for **retries, timeouts, and caching** to each action. Caching is critical for idempotency and efficiency on re-runs.

## 4. Data Models

We will use Pydantic models to ensure data consistency throughout the pipeline.

```python
# To be defined in models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class BookmarkInput(BaseModel):
    id: int
    url: str
    tags: List[str]

class LivenessResult(BaseModel):
    status: Literal["success", "failed"]
    method: Optional[Literal["head_then_get", "get", "headless"]] = None
    final_url: Optional[str] = None
    content: Optional[str] = None # HTML content
    error_message: Optional[str] = None

class ProcessedBookmarkOutput(BaseModel):
    source_id: int
    source_url: str
    final_url: str
    status: Literal["processed", "failed"]
    summary: Optional[str] = None
    suggested_tags: List[str] = []
    linting_warnings: List[str] = []
    failure_reason: Optional[str] = None
```

## 5. Workflow Implementation Details

### 5.1. Top-Level Flow: `process_all_bookmarks_flow`

  * **Decorator:** `@flow(name="Process All Bookmarks", task_runner=ConcurrentTaskRunner())`
  * **Input:** `bookmarks_filepath: str`
  * **Logic:**
    1.  Read the bookmarks from the input JSON file into a list of `BookmarkInput` models.
    2.  Iterate through the list.
    3.  For each bookmark, submit a `process_bookmark_flow` run: `process_bookmark_flow.submit(bookmark)`.

### 5.2. Bookmark Subflow: `process_bookmark_flow`

  * **Decorator:** `@flow(name="Process Single Bookmark")`
  * **Input:** `bookmark: BookmarkInput`
  * **Logic:**
    1.  Call the `liveness_flow` with `bookmark.url`.
    2.  Use a `try...except LivenessCheckFailed` block to handle total failure of the liveness check. If it fails, create a `ProcessedBookmarkOutput` with `status="failed"` and save it.
    3.  If `liveness_flow` succeeds, extract the HTML `content` from its result.
    4.  Call `extract_main_content(content)` to get clean text.
    5.  Submit the following tasks to run in parallel:
          * `summarize_content.submit(clean_text)`
          * `suggest_tags.submit(clean_text)`
          * `lint_tags.submit(bookmark.tags)`
    6.  Wait for the parallel tasks to complete and gather their results.
    7.  Assemble the final `ProcessedBookmarkOutput` model with `status="processed"`.
    8.  Call a final task `save_result(output_model)` to write the result to a file or database.

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
      * Action: Compare input tags against a predefined "blessed" list. Return a list of warnings.
  * **`summarize_content(text: str) -> str`**
      * Decorator: `@task(**CACHE_SETTINGS)`
      * Action: Call the external/local LLM API with the text to generate a summary.
  * **`suggest_tags(text: str) -> List[str]`**
      * Decorator: `@task(**CACHE_SETTINGS)`
      * Action: Call the external/local LLM API to suggest relevant tags.
  * **`save_result(result: ProcessedBookmarkOutput)`**
      * Decorator: `@task`
      * Action: Append the processed result to a master output JSON file. This task must be designed to handle concurrent writes safely (e.g., using a file lock).

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
|   |-- io.py           # Contains save_result task
|-- bookmarks_input.json # Example input data
|-- pyproject.toml      # Project configuration for uv, ruff, and pytest
|-- prefect.yaml        # Prefect deployment configuration (optional)
```

## 7. Testing Strategy

*   **Unit Tests:** Each task will be tested in isolation. For example, `extract_main_content` will be tested with sample HTML strings, and `lint_tags` will be tested with various tag lists.
*   **Integration Tests:** The interaction between tasks within a flow will be tested. This will involve mocking external services. HTTP requests made with `httpx` will be mocked using the `respx` library, and LLM API calls will be mocked using `pytest-mock`.
*   **Flow Tests:** The `liveness_flow` and `process_bookmark_flow` will be tested as units, using Prefect's testing utilities to run them synchronously and assert their outcomes against mock data.

