import pytest
from prefect.testing.utilities import prefect_test_harness
from prefect.logging import disable_run_logger
from bookmark_processor.main import (
    liveness_flow,
    process_bookmark_flow,
    _get_and_extract_content_source,
    _summarize_and_update_extended,
    _suggest_and_add_new_tags,
    _lint_and_filter_tags,
)
from bookmark_processor.models import Bookmark, LivenessResult


@pytest.fixture(autouse=True, scope="module")
def prefect_test_fixture():
    """
    Fixture to run tests within a Prefect test harness.
    """
    with prefect_test_harness():
        yield


# --- Tests for liveness_flow ---


def test_liveness_flow_get_success(mocker):
    """
    Tests liveness_flow when attempt_get_request succeeds.
    """
    mock_get = mocker.patch(
        "bookmark_processor.main.attempt_get_request",
        return_value={
            "final_url": "http://example.com/final",
            "content": "<html>GET</html>",
            "status_code": 200,
        },
    )
    mock_headless = mocker.patch(
        "bookmark_processor.main.attempt_headless_browser", return_value=None
    )

    with disable_run_logger():
        result = liveness_flow(url="http://example.com")

    assert result.is_live is True
    assert result.method == "GET"
    assert result.final_url == "http://example.com/final"
    assert result.content == "<html>GET</html>"
    assert result.status_code == 200
    mock_get.assert_called_once_with("http://example.com")
    mock_headless.assert_not_called()


def test_liveness_flow_headless_fallback_success(mocker):
    """
    Tests liveness_flow when GET fails but headless browser succeeds.
    """
    mock_get = mocker.patch(
        "bookmark_processor.main.attempt_get_request", return_value=None
    )
    mock_headless = mocker.patch(
        "bookmark_processor.main.attempt_headless_browser",
        return_value={
            "final_url": "http://example.com/final_headless",
            "content": "<html>HEADLESS</html>",
            "status_code": 200,
        },
    )

    with disable_run_logger():
        result = liveness_flow(url="http://example.com")

    assert result.is_live is True
    assert result.method == "HEADLESS"
    assert result.final_url == "http://example.com/final_headless"
    assert result.content == "<html>HEADLESS</html>"
    assert result.status_code == 200
    mock_get.assert_called_once_with("http://example.com")
    mock_headless.assert_called_once_with("http://example.com")


def test_liveness_flow_all_checks_fail(mocker):
    """
    Tests liveness_flow when both GET and headless browser checks fail.
    """
    mock_get = mocker.patch(
        "bookmark_processor.main.attempt_get_request", return_value=None
    )
    mock_headless = mocker.patch(
        "bookmark_processor.main.attempt_headless_browser", return_value=None
    )

    with disable_run_logger():
        result = liveness_flow(url="http://example.com")

    assert result.is_live is False
    assert result.method == "NONE"
    assert result.final_url is None
    assert result.content is None
    assert result.status_code is None
    mock_get.assert_called_once_with("http://example.com")
    mock_headless.assert_called_once_with("http://example.com")


# --- Tests for _get_and_extract_content_source ---


def test_get_and_extract_content_source_from_extended():
    """
    Tests that _get_and_extract_content_source uses bookmark.extended if available.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="Existing extended content.",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    liveness_result = LivenessResult(
        url="http://example.com", is_live=True, method="GET", content="<html></html>"
    )

    with disable_run_logger():
        result = _get_and_extract_content_source(bookmark, liveness_result)

    assert result == "Existing extended content."


def test_get_and_extract_content_source_from_liveness_result(mocker):
    """
    Tests that _get_and_extract_content_source uses liveness_result.content
    and calls extract_main_content if bookmark.extended is empty.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    liveness_result = LivenessResult(
        url="http://example.com",
        is_live=True,
        method="GET",
        content="<html><body>Main content</body></html>",
    )

    mock_extract = mocker.patch(
        "bookmark_processor.main.extract_main_content", return_value="Main content"
    )
    mock_get_request = mocker.patch("bookmark_processor.main.attempt_get_request")

    with disable_run_logger():
        result = _get_and_extract_content_source(bookmark, liveness_result)

    assert result == "Main content"
    mock_extract.assert_called_once_with("<html><body>Main content</body></html>")
    mock_get_request.assert_not_called()


def test_get_and_extract_content_source_fallback_to_direct_get(mocker):
    """
    Tests that _get_and_extract_content_source falls back to direct GET
    if both bookmark.extended and liveness_result.content are empty.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    liveness_result = LivenessResult(
        url="http://example.com", is_live=True, method="GET", content=None
    )

    mock_extract = mocker.patch(
        "bookmark_processor.main.extract_main_content",
        return_value="Content from direct GET",
    )
    mock_get_request = mocker.patch(
        "bookmark_processor.main.attempt_get_request",
        return_value={
            "content": "<html>Direct GET content</html>",
            "final_url": "http://example.com",
            "status_code": 200,
        },
    )

    with disable_run_logger():
        result = _get_and_extract_content_source(bookmark, liveness_result)

    assert result == "Content from direct GET"
    mock_get_request.assert_called_once_with("http://example.com")
    mock_extract.assert_called_once_with("<html>Direct GET content</html>")


def test_get_and_extract_content_source_no_content_at_all(mocker):
    """
    Tests that _get_and_extract_content_source returns None if no content can be found.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    liveness_result = LivenessResult(
        url="http://example.com", is_live=True, method="GET", content=None
    )

    mock_extract = mocker.patch(
        "bookmark_processor.main.extract_main_content",
        return_value="",  # Simulate extract_main_content returning empty
    )
    mock_get_request = mocker.patch(
        "bookmark_processor.main.attempt_get_request",
        return_value={
            "content": "",
            "final_url": "http://example.com",
            "status_code": 200,
        },  # Simulate empty content from direct GET
    )

    with disable_run_logger():
        result = _get_and_extract_content_source(bookmark, liveness_result)

    assert result is None
    mock_get_request.assert_called_once_with("http://example.com")
    mock_extract.assert_called_once_with(
        ""
    )  # This assertion should now pass with the main.py change


# --- Tests for _summarize_and_update_extended ---


def test_summarize_and_update_extended_summarizes_when_empty(mocker):
    """
    Tests that _summarize_and_update_extended calls summarize_content
    and updates bookmark.extended if it's empty.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    text_source = "Long text to summarize."
    mock_summarize = mocker.patch(
        "bookmark_processor.main.summarize_content", return_value="A short summary."
    )

    with disable_run_logger():
        _summarize_and_update_extended(bookmark, text_source)

    assert bookmark.extended == "A short summary."
    mock_summarize.assert_called_once_with(text_source)


def test_summarize_and_update_extended_does_not_summarize_when_not_empty(mocker):
    """
    Tests that _summarize_and_update_extended does not call summarize_content
    if bookmark.extended already has content.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="Already has content.",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    text_source = "Long text to summarize."
    mock_summarize = mocker.patch("bookmark_processor.main.summarize_content")

    with disable_run_logger():
        _summarize_and_update_extended(bookmark, text_source)

    assert bookmark.extended == "Already has content."
    mock_summarize.assert_not_called()


def test_summarize_and_update_extended_no_text_source(mocker):
    """
    Tests that _summarize_and_update_extended does not call summarize_content
    if text_source is None.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    text_source = None
    mock_summarize = mocker.patch("bookmark_processor.main.summarize_content")

    with disable_run_logger():
        _summarize_and_update_extended(bookmark, text_source)

    assert bookmark.extended == ""
    mock_summarize.assert_not_called()


# --- Tests for _suggest_and_add_new_tags ---


def test_suggest_and_add_new_tags_adds_tags(mocker):
    """
    Tests that _suggest_and_add_new_tags calls suggest_tags and adds new tags.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=["existing"],
    )
    text_source = "Content for tags."
    mock_suggest_tags = mocker.patch(
        "bookmark_processor.main.suggest_tags", return_value=["new-tag", "another-tag"]
    )

    with disable_run_logger():
        _suggest_and_add_new_tags(bookmark, text_source)

    assert sorted(bookmark.tags) == sorted(["existing", "new-tag", "another-tag"])
    mock_suggest_tags.assert_called_once_with(text_source)


def test_suggest_and_add_new_tags_no_text_source(mocker):
    """
    Tests that _suggest_and_add_new_tags does not call suggest_tags if text_source is None.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=["existing"],
    )
    text_source = None
    mock_suggest_tags = mocker.patch("bookmark_processor.main.suggest_tags")

    with disable_run_logger():
        _suggest_and_add_new_tags(bookmark, text_source)

    assert bookmark.tags == ["existing"]
    mock_suggest_tags.assert_not_called()


# --- Tests for _lint_and_filter_tags ---


def test_lint_and_filter_tags_removes_unblessed(mocker):
    """
    Tests that _lint_and_filter_tags calls lint_tags and updates bookmark.tags.
    """
    bookmark = Bookmark(
        href="http://example.com",
        description="Test",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=["python", "gossip", "ai"],
    )
    blessed_tags_set = {"python", "ai", "prefect"}
    mock_lint_tags = mocker.patch(
        "bookmark_processor.main.lint_tags", return_value=["python", "ai"]
    )

    with disable_run_logger():
        _lint_and_filter_tags(bookmark, blessed_tags_set)

    assert bookmark.tags == ["python", "ai"]
    mock_lint_tags.assert_called_once_with(["python", "gossip", "ai"], blessed_tags_set)


# --- Tests for process_bookmark_flow ---


def test_process_bookmark_flow_not_live(mocker):
    """
    Tests that process_bookmark_flow correctly handles a non-live bookmark:
    tags it with 'not-live' and skips content processing.
    """
    bookmark = Bookmark(
        href="http://example.com/dead",
        description="Dead Link",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=["old"],
    )
    blessed_tags_set = {"old", "not-live"}

    # Mock liveness_flow to return a non-live result
    mocker.patch(
        "bookmark_processor.main.liveness_flow",
        return_value=LivenessResult(
            url="http://example.com/dead",
            is_live=False,
            status_code=None,
            method="NONE",
            final_url=None,
            content=None,
        ),
    )
    # Mock content processing tasks to ensure they are NOT called
    mock_get_and_extract = mocker.patch(
        "bookmark_processor.main._get_and_extract_content_source"
    )
    mock_summarize = mocker.patch(
        "bookmark_processor.main._summarize_and_update_extended"
    )
    mock_suggest_tags = mocker.patch(
        "bookmark_processor.main._suggest_and_add_new_tags"
    )
    mock_lint_tags = mocker.patch(
        "bookmark_processor.main._lint_and_filter_tags", wraps=_lint_and_filter_tags
    )  # Use wraps to allow actual linting

    with disable_run_logger():
        processed_bookmark = process_bookmark_flow(bookmark, blessed_tags_set)

    assert processed_bookmark.href == "http://example.com/dead"
    assert "not-live" in processed_bookmark.tags
    assert "old" in processed_bookmark.tags  # Should still lint existing tags
    assert processed_bookmark.extended == ""  # Should not be summarized
    mock_get_and_extract.assert_not_called()
    mock_summarize.assert_not_called()
    mock_suggest_tags.assert_not_called()
    mock_lint_tags.assert_called_once()  # lint_tags should still be called


def test_process_bookmark_flow_redirect_updates_href(mocker):
    """
    Tests that process_bookmark_flow updates bookmark.href if liveness check
    results in a redirect (final_url is different).
    """
    bookmark = Bookmark(
        href="http://example.com/old",
        description="Redirected Link",
        extended="",
        meta="",
        hash="",
        time="",
        shared="",
        toread="",
        tags=[],
    )
    blessed_tags_set = set()

    # Mock liveness_flow to return a live result with a redirect
    mocker.patch(
        "bookmark_processor.main.liveness_flow",
        return_value=LivenessResult(
            url="http://example.com/old",
            is_live=True,
            status_code=200,
            method="GET",
            final_url="http://example.com/new",  # Different final_url
            content="<html>New content</html>",
        ),
    )
    # Mock content processing tasks to allow flow to continue
    mocker.patch(
        "bookmark_processor.main._get_and_extract_content_source",
        return_value="content",
    )
    mocker.patch("bookmark_processor.main._summarize_and_update_extended")
    mocker.patch("bookmark_processor.main._suggest_and_add_new_tags")
    mocker.patch("bookmark_processor.main._lint_and_filter_tags")

    with disable_run_logger():
        processed_bookmark = process_bookmark_flow(bookmark, blessed_tags_set)

    assert processed_bookmark.href == "http://example.com/new"
