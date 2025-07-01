import json
from pathlib import Path
import pytest
from prefect.testing.utilities import prefect_test_harness
from bookmark_processor.main import process_all_bookmarks_flow
from bookmark_processor.models import Bookmark, LivenessResult

TEST_BOOKMARKS_CONTENT = """
[
    {
        "href": "http://example.com/page1",
        "description": "Example Page One",
        "extended": "",
        "meta": "e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
        "hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "time": "2023-01-01T10:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "tech programming"
    },
    {
        "href": "http://example.com/page2",
        "description": "Example Page Two",
        "extended": "This is a pre-existing extended description for page 2.",
        "meta": "f1e2d3c4b5a69876543210fedcba9876",
        "hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "time": "2023-01-02T11:00:00Z",
        "shared": "no",
        "toread": "yes",
        "tags": "science"
    }
]
"""


@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    """
    Fixture to run tests within a Prefect test harness, providing an isolated
    temporary local SQLite database for Prefect operations.
    """
    with prefect_test_harness():
        yield


def test_process_all_bookmarks_flow_integration(tmp_path: Path, mocker):
    """
    Tests the end-to-end processing flow for all bookmarks.
    """
    # Create temporary input file path (content is mocked)
    input_file = tmp_path / "test_input.json"
    output_file = tmp_path / "test_output.json"

    # Define a side effect function for liveness_flow mock
    def mock_liveness_flow_side_effect(url: str) -> LivenessResult:
        """Returns a LivenessResult where final_url matches the input url."""
        return LivenessResult(
            url=url,
            is_live=True,
            status_code=200,
            content="<html><body><h1>Test Content</h1><p>This is some test content for summarization and tag suggestion. It talks about machine learning and artificial intelligence.</p></body></html>",
            method="HEADLESS",
            final_url=url,  # Ensure final_url matches the input url
        )

    # Mock Prefect tasks and flows
    mocker.patch(
        "bookmark_processor.main.liveness_flow",
        side_effect=mock_liveness_flow_side_effect,
    )
    mocker.patch(
        "bookmark_processor.main.load_bookmarks",
        return_value=json.loads(TEST_BOOKMARKS_CONTENT),
    )
    mocker.patch(
        "bookmark_processor.main.load_blessed_tags",
        return_value={"tech", "programming", "science"},
    )
    mocker.patch(
        "bookmark_processor.main.extract_main_content",
        return_value="Test content about machine learning and AI.",
    )
    mocker.patch(
        "bookmark_processor.main.summarize_content",
        return_value="A concise summary of test content.",
    )
    mocker.patch(
        "bookmark_processor.main.suggest_tags",
        return_value=["machine-learning", "ai", "technology"],
    )
    mocker.patch(
        "bookmark_processor.main.lint_tags",
        side_effect=lambda tags, blessed: [t for t in tags if t in blessed],
    )
    mock_save_results = mocker.patch("bookmark_processor.main.save_results")

    # Run the flow
    process_all_bookmarks_flow(str(input_file), str(output_file))

    # Assertions
    # Verify that save_results was called with the correct output path
    mock_save_results.assert_called_once()
    args, kwargs = mock_save_results.call_args
    assert args[1] == str(output_file)

    # Verify the content of the processed bookmarks passed to save_results
    processed_bookmarks_list = args[0]
    assert len(processed_bookmarks_list) == 2

    # Check first bookmark (should be summarized)
    b1 = processed_bookmarks_list[0]
    assert isinstance(b1, Bookmark)
    assert b1.href == "http://example.com/page1"
    assert b1.extended == "A concise summary of test content."
    assert sorted(b1.tags) == sorted(["tech", "programming"])

    # Check second bookmark (should retain its original extended description)
    b2 = processed_bookmarks_list[1]
    assert isinstance(b2, Bookmark)
    assert b2.href == "http://example.com/page2"
    assert b2.extended == "This is a pre-existing extended description for page 2."
    assert sorted(b2.tags) == sorted(["science"])
