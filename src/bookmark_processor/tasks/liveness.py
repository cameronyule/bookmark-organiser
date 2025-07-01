import requests
from typing import Optional, Dict, Any
from datetime import timedelta
from prefect import task
from prefect.tasks import task_input_hash

CACHE_SETTINGS = dict(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))

@task(retries=2, retry_delay_seconds=10, **CACHE_SETTINGS)
def attempt_get_request(url: str) -> Optional[Dict[str, Any]]:
    """
    Attempts a GET request to the given URL.
    Returns status code, content type, and HTML content if successful.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return {
            "status_code": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "html_content": response.text,
        }
    except requests.exceptions.RequestException as e:
        print(f"GET request failed for {url}: {e}")
        return None

@task(retries=1, retry_delay_seconds=30, **CACHE_SETTINGS)
def attempt_headless_browser(url: str) -> Optional[Dict[str, Any]]:
    """
    Attempts to retrieve content using a headless browser (Selenium).
    This task is intended to be called from a flow that manages the WebDriver.
    It returns a dummy dictionary as the actual content retrieval is handled
    by prefect-selenium tasks in the main flow.
    """
    # This task is a placeholder. The actual headless browser logic
    # is handled by prefect-selenium tasks (open_webpage, get_page_content)
    # in the main flow, which directly interact with the WebDriver.
    # This task exists primarily for caching purposes if needed,
    # but its return value here is not directly used for content.
    # The content will be passed from the flow.
    print(f"Headless browser check initiated for {url}. Content will be retrieved by Prefect Selenium tasks.")
    return {"status_code": 200, "content_type": "text/html", "html_content": "PLACEHOLDER_CONTENT"}
