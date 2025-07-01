import json
from pathlib import Path
import pytest
from prefect.testing.utilities import prefect_test_harness # Import prefect_test_harness
from bookmark_processor.main import process_all_bookmarks_flow
from bookmark_processor.models import Bookmark, LivenessResult

# Define paths relative to the project root for tests
TEST_BOOKMARKS_INPUT_PATH = "tests/test_bookmarks_input.json"
TEST_BLESSED_TAGS_PATH = "blessed_tags.txt" # Now at project root
TEST_OUTPUT_PATH = "tests/processed_bookmarks_output.json"

TEST_BOOKMARKS_CONTENT = """
[
    {
        "href": "http://example.com/page1",
        "description": "Example Page One",
        "extended": "A test page for integration.",
        "meta": "e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
        "hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "time": "2023-01-01T10:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "tech, programming"
    },
    {
        "href": "http://example.com/page2",
        "description": "Example Page Two",
        "extended": "Another test page.",
        "meta": "f1e2d3c4b5a69876543210fedcba9876",
        "hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
        "time": "2023-01-02T11:00:00Z",
        "shared": "no",
        "toread": "yes",
        "tags": "science"
    }
]
"""

TEST_BLESSED_TAGS_CONTENT = "tech\nprogramming\nscience\n"

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    """
    Fixture to run tests within a Prefect test harness, providing an isolated
    temporary local SQLite database for Prefect operations.
    """
    with prefect_test_harness():
        yield

@pytest.fixture
def mock_liveness_result():
    """Fixture to provide a mock LivenessResult.
    This fixture is no longer directly used as return_value for liveness_flow,
    but kept for reference or if needed elsewhere.
    """
    return LivenessResult(
        url="http://mock.com/test_page",
        is_live=True,
        status_code=200,
        content="<html><body><h1>Test Content</h1><p>This is some test content for summarization and tag suggestion. It talks about machine learning and artificial intelligence.</p></body></html>",
        method="HEADLESS",
        final_url="http://mock.com/test_page",
    )

def test_process_all_bookmarks_flow_integration(tmp_path: Path, mocker): # Removed mock_liveness_result from args
    """
    Tests the end-to-end processing flow for all bookmarks.
    """
    # Create temporary input files
    input_file = tmp_path / "test_bookmarks_input.json"
    input_file.write_text(TEST_BOOKMARKS_CONTENT)

    blessed_tags_file = tmp_path / "blessed_tags.txt"
    blessed_tags_file.write_text(TEST_BLESSED_TAGS_CONTENT)

    output_file = tmp_path / "processed_bookmarks_output.json"

    # Define a side effect function for liveness_flow mock
    def mock_liveness_flow_side_effect(url: str) -> LivenessResult:
        """Returns a LivenessResult where final_url matches the input url."""
        return LivenessResult(
            url=url,
            is_live=True,
            status_code=200,
            content="<html><body><h1>Test Content</h1><p>This is some test content for summarization and tag suggestion. It talks about machine learning and artificial intelligence.</p></body></html>",
            method="HEADLESS",
            final_url=url, # Ensure final_url matches the input url
        )

    # Mock Prefect tasks and flows
    mocker.patch("bookmark_processor.main.liveness_flow", side_effect=mock_liveness_flow_side_effect) # Use side_effect
    # Patch load_bookmarks where it's used in main.py
    mocker.patch("bookmark_processor.main.load_bookmarks", return_value=json.loads(TEST_BOOKMARKS_CONTENT))
    # Patch save_results where it's used in main.py
    mock_save_results = mocker.patch("bookmark_processor.main.save_results") # Capture the mock object
    mocker.patch("bookmark_processor.tasks.processing.load_blessed_tags", return_value={"tech", "programming", "science"})
    mocker.patch("bookmark_processor.tasks.processing.extract_main_content", return_value="Test content about machine learning and AI.")
    mocker.patch("bookmark_processor.tasks.processing.summarize_content", return_value="A concise summary of test content.")
    mocker.patch("bookmark_processor.tasks.processing.suggest_tags", return_value=["machine-learning", "ai", "technology"])
    mocker.patch("bookmark_processor.tasks.processing.lint_tags", side_effect=lambda tags, blessed: [t for t in tags if t in blessed])


    # Run the flow
    process_all_bookmarks_flow(str(input_file), str(output_file))

    # Assertions
    # Verify that save_results was called with the correct output path
    mock_save_results.assert_called_once() # Use the captured mock object
    args, kwargs = mock_save_results.call_args # Use the captured mock object
    assert args[1] == str(output_file)

    # Verify the content of the processed bookmarks passed to save_results
    processed_bookmarks_list = args[0]
    assert len(processed_bookmarks_list) == 2

    # Check first bookmark
    b1 = processed_bookmarks_list[0]
    assert isinstance(b1, Bookmark)
    assert b1.href == "http://example.com/page1" # This assertion will now pass
    assert b1.liveness.is_live is True
    assert b1.extended_description == "A concise summary of test content."
    # Check tags: original + suggested, then linted
    # Original: tech, programming. Suggested: machine-learning, ai, technology. Blessed: tech, programming, science
    # Expected: tech, programming, machine-learning, ai, technology (before linting)
    # After linting with blessed_tags_set={"tech", "programming", "science"}:
    # The mock lint_tags will filter based on the blessed set.
    # The suggested tags "machine-learning", "ai", "technology" are NOT in the blessed set.
    # So, the final tags should only be the original blessed ones.
    # However, the mock for suggest_tags returns "machine-learning", "ai", "technology".
    # The mock for lint_tags is `lambda tags, blessed: [t for t in tags if t in blessed]`.
    # So, if the suggested tags are added, and then linted, they will be removed if not blessed.
    # Let's refine the expected tags based on the mock linting.
    # Initial: ["tech", "programming"]
    # After suggest_tags: ["tech", "programming", "machine-learning", "ai", "technology"]
    # After lint_tags (with blessed={"tech", "programming", "science"}):
    # Only "tech" and "programming" should remain.
    assert sorted(b1.tags) == sorted(["tech", "programming"])


    # Check second bookmark
    b2 = processed_bookmarks_list[1]
    assert isinstance(b2, Bookmark)
    assert b2.href == "http://example.com/page2" # This assertion will now pass
    assert b2.liveness.is_live is True
    assert b2.extended_description == "A concise summary of test content."
    # Original: science. Suggested: machine-learning, ai, technology. Blessed: tech, programming, science
    # After linting: only "science" should remain.
    assert sorted(b2.tags) == sorted(["science"])

    # Verify that the output file was attempted to be saved (even if mocked)
    assert output_file.exists() # This will be true if save_results was called and the mock didn't prevent file creation
