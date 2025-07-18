from unittest.mock import MagicMock

import httpx

from bookmark_processor.tasks.liveness import (
    attempt_get_request,
    attempt_headless_browser,
)


def test_attempt_get_request_success(mocker):
    """
    Tests that attempt_get_request returns a dictionary on a successful GET request.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html>Success</html>"
    mock_response.url = "http://example.com/final"
    mock_response.raise_for_status.return_value = None

    mock_client_context = mocker.patch("httpx.Client")
    mock_client = mock_client_context.return_value.__enter__.return_value
    mock_client.get.return_value = mock_response

    # Act
    result = attempt_get_request.fn("http://example.com")

    # Assert
    assert result == {
        "final_url": "http://example.com/final",
        "content": "<html>Success</html>",
        "status_code": 200,
    }
    mock_client.get.assert_called_once_with("http://example.com", timeout=20)


def test_attempt_get_request_failure(mocker):
    """
    Tests that attempt_get_request returns None when the request fails.
    """
    # Arrange
    mock_client_context = mocker.patch("httpx.Client")
    mock_client = mock_client_context.return_value.__enter__.return_value
    mock_request = MagicMock()
    mock_client.get.side_effect = httpx.RequestError("mock error", request=mock_request)

    # Act
    result = attempt_get_request.fn("http://example.com")

    # Assert
    assert result is None


def test_attempt_headless_browser_success(mocker):
    """
    Tests that attempt_headless_browser returns a dictionary on a successful page load.
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
    mock_response.status = 200
    mock_page.goto.return_value = mock_response
    mock_page.content.return_value = "<html>Success</html>"
    mock_page.url = "http://example.com/final"

    # Act
    result = attempt_headless_browser.fn("http://example.com")

    # Assert
    assert result == {
        "final_url": "http://example.com/final",
        "content": "<html>Success</html>",
        "status_code": 200,
    }
    mock_page.goto.assert_called_once_with(
        "http://example.com", wait_until="domcontentloaded", timeout=60000
    )
    mock_browser.close.assert_called_once()


def test_attempt_headless_browser_failure(mocker):
    """
    Tests that attempt_headless_browser returns None when an exception occurs.
    """
    # Arrange
    mock_sync_playwright = mocker.patch(
        "bookmark_processor.tasks.liveness.sync_playwright"
    )
    mock_playwright_context = mock_sync_playwright.return_value.__enter__.return_value
    mock_browser = mock_playwright_context.chromium.launch.return_value
    mock_browser_context = mock_browser.new_context.return_value
    mock_page = mock_browser_context.new_page.return_value
    mock_page.goto.side_effect = Exception("mock error")

    # Act
    result = attempt_headless_browser.fn("http://example.com")

    # Assert
    assert result is None
    mock_browser.close.assert_called_once()
