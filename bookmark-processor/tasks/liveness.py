from datetime import timedelta

import httpx
from playwright.sync_api import sync_playwright
from prefect import task
from prefect.tasks import task_input_hash

CACHE_SETTINGS = dict(
    cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7)
)


class LivenessCheckFailed(Exception):
    """Custom exception to signal a URL is not live."""

    pass


@task(retries=2, retry_delay_seconds=5, **CACHE_SETTINGS)
def attempt_head_request(url: str) -> str:
    """
    Use httpx to make a HEAD request. Follow redirects. Return the final URL.
    """
    with httpx.Client(follow_redirects=True) as client:
        response = client.head(url, timeout=10)
        response.raise_for_status()
        return str(response.url)


@task(retries=2, retry_delay_seconds=10, **CACHE_SETTINGS)
def attempt_get_request(url: str) -> dict:
    """
    Use httpx to make a GET request. Return a dict {"final_url": str, "content": str}.
    """
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url, timeout=20)
        response.raise_for_status()
        return {"final_url": str(response.url), "content": response.text}


@task(retries=1, retry_delay_seconds=30, **CACHE_SETTINGS)
def attempt_headless_browser(url: str) -> dict:
    """
    Use playwright to load the page. Return a dict {"final_url": str, "content": str}.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            content = page.content()
            final_url = page.url
        finally:
            browser.close()
        return {"final_url": final_url, "content": content}
