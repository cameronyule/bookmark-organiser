from datetime import timedelta
from typing import Any, Dict, Optional

import httpx
from playwright.sync_api import sync_playwright
from prefect import task
from prefect.tasks import task_input_hash

CACHE_SETTINGS = dict(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))


@task(retries=2, retry_delay_seconds=10, **CACHE_SETTINGS)
def attempt_get_request(url: str) -> Optional[Dict[str, Any]]:
    """
    Use httpx to make a GET request. Return a dict {"final_url": str, "content": str, "status_code": int}.
    Returns None if the request fails.
    """
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url, timeout=20)
            response.raise_for_status()
            return {
                "final_url": str(response.url),
                "content": response.text,
                "status_code": response.status_code,
            }
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None


@task(retries=1, retry_delay_seconds=30, **CACHE_SETTINGS)
def attempt_headless_browser(url: str) -> Optional[Dict[str, Any]]:
    """
    Use playwright to load the page. Return a dict {"final_url": str, "content": str, "status_code": int}.
    Returns None if the request fails.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                content = page.content()
                final_url = page.url
                if response:
                    status_code = response.status
                else:
                    # If no response, but we have content, it's likely a successful
                    # client-side redirect (e.g. Cloudflare). Assume success.
                    # If no content, it could be a 204 No Content, so we can't
                    # assume a status code.
                    status_code = 200 if content else None
            finally:
                browser.close()
            return {
                "final_url": final_url,
                "content": content,
                "status_code": status_code,
            }
    except Exception:
        return None
