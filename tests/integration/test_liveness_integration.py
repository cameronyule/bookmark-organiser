from unittest.mock import MagicMock

import httpx
import pytest

from bookmark_processor.tasks.liveness import (
    attempt_get_request,
    attempt_headless_browser,
)


@pytest.mark.parametrize(
    "status_code",
    [404, 500],
)
def test_attempt_get_request_handles_http_errors(mocker, status_code):
    """
    Tests that attempt_get_request returns None for HTTP error status codes
    by checking that raise_for_status is called.
    """
    # Arrange
    url = "http://example.com"
    mock_request = MagicMock()
    mock_request.url = url
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"Mock {status_code} error", request=mock_request, response=mock_response
    )

    mock_client_context = mocker.patch("httpx.Client")
    mock_client = mock_client_context.return_value.__enter__.return_value
    mock_client.get.return_value = mock_response

    # Act
    result = attempt_get_request.fn(url)

    # Assert
    assert result is None
    mock_response.raise_for_status.assert_called_once()


def test_attempt_get_request_handles_redirects(mocker):
    """
    Tests that attempt_get_request correctly reports the final URL after a redirect.
    """
    # Arrange
    initial_url = "http://example.com"
    final_url = "http://example.com/redirected"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html>Redirected content</html>"
    mock_response.url = final_url
    mock_response.raise_for_status.return_value = None

    mock_client_context = mocker.patch("httpx.Client")
    mock_client = mock_client_context.return_value.__enter__.return_value
    mock_client.get.return_value = mock_response

    # Act
    result = attempt_get_request.fn(initial_url)

    # Assert
    assert result is not None
    assert result["final_url"] == final_url
    assert result["content"] == "<html>Redirected content</html>"
    mock_client_context.assert_called_once_with(follow_redirects=True)
    mock_client.get.assert_called_once_with(initial_url, timeout=20)


def test_attempt_headless_browser_handles_none_response(mocker):
    """
    Tests that attempt_headless_browser handles a None response from page.goto,
    which can occur for 204 No Content responses.
    """
    # Arrange
    mock_sync_playwright = mocker.patch(
        "bookmark_processor.tasks.liveness.sync_playwright"
    )
    mock_playwright_context = mock_sync_playwright.return_value.__enter__.return_value
    mock_browser = mock_playwright_context.chromium.launch.return_value
    mock_browser_context = mock_browser.new_context.return_value
    mock_page = mock_browser_context.new_page.return_value

    mock_page.goto.return_value = None
    mock_page.content.return_value = ""
    mock_page.url = "http://example.com/final"

    # Act
    result = attempt_headless_browser.fn("http://example.com")

    # Assert
    assert result == {
        "content": "",
        "final_url": "http://example.com/final",
        "status_code": None,
    }
    mock_browser.close.assert_called_once()


def test_attempt_headless_browser_uses_context(mocker):
    """
    Tests that attempt_headless_browser correctly uses and closes a BrowserContext.
    """
    # Arrange
    mock_sync_playwright = mocker.patch(
        "bookmark_processor.tasks.liveness.sync_playwright"
    )
    mock_playwright_context = mock_sync_playwright.return_value.__enter__.return_value
    mock_browser = mock_playwright_context.chromium.launch.return_value
    mock_context = mock_browser.new_context.return_value
    mock_page = mock_context.new_page.return_value

    mock_page.goto.return_value = mocker.MagicMock(
        status=200, url="http://example.com/final"
    )
    mock_page.content.return_value = "<html>test content</html>"
    mock_page.url = "http://example.com/final"

    # Act
    attempt_headless_browser.fn("http://example.com")

    # Assert
    mock_browser.new_context.assert_called_once()
    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()


@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
def test_attempt_headless_browser_http_error_status(mocker, status_code):
    """
    Tests that attempt_headless_browser returns None for 4xx/5xx HTTP status codes.
    """
    # Arrange
    mock_sync_playwright = mocker.patch(
        "bookmark_processor.tasks.liveness.sync_playwright"
    )
    mock_playwright_context = mock_sync_playwright.return_value.__enter__.return_value
    mock_browser = mock_playwright_context.chromium.launch.return_value
    mock_browser_context = mock_browser.new_context.return_value
    mock_page = mock_browser_context.new_page.return_value

    mock_response = MagicMock()
    mock_response.status = status_code
    mock_page.goto.return_value = mock_response
    mock_page.content.return_value = "<html>Error Page</html>"
    mock_page.url = f"http://example.com/error/{status_code}"

    # Act
    result = attempt_headless_browser(f"http://example.com/test/{status_code}")

    # Assert
    assert result is None
    mock_browser_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
