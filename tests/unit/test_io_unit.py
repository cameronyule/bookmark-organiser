import json
import pytest
from prefect.logging import disable_run_logger
from bookmark_processor.tasks.io import load_bookmarks, save_results
from bookmark_processor.models import Bookmark

# --- Tests for load_bookmarks ---


def test_load_bookmarks_success(fs):
    """
    Tests that load_bookmarks correctly loads data from a valid JSON file.
    """
    filepath = "test_bookmarks.json"
    content = [
        {"href": "url1", "description": "desc1", "tags": "tag1 tag2"},
        {"href": "url2", "description": "desc2", "tags": "tag3"},
    ]
    fs.create_file(filepath, contents=json.dumps(content))

    with disable_run_logger():
        result = load_bookmarks.fn(filepath)

    assert result == content


def test_load_bookmarks_file_not_found(fs):
    """
    Tests that load_bookmarks raises FileNotFoundError if the file does not exist.
    """
    filepath = "non_existent.json"
    with pytest.raises(FileNotFoundError):
        with disable_run_logger():
            load_bookmarks.fn(filepath)


def test_load_bookmarks_malformed_json(fs):
    """
    Tests that load_bookmarks raises json.JSONDecodeError for malformed JSON.
    """
    filepath = "malformed.json"
    fs.create_file(filepath, contents="[ { 'href': 'url1', }")  # Malformed JSON

    with pytest.raises(json.JSONDecodeError):
        with disable_run_logger():
            load_bookmarks.fn(filepath)


# --- Tests for save_results ---


@pytest.fixture
def sample_bookmarks():
    """Provides a list of Bookmark objects for testing save_results."""
    return [
        Bookmark(
            href="http://example.com/page1",
            description="Example Page One",
            extended="A concise summary.",
            meta="e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
            hash="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            time="2023-01-01T10:00:00Z",
            shared="yes",
            toread="no",
            tags=["tech", "programming"],
        ),
        Bookmark(
            href="http://example.com/page2",
            description="Example Page Two",
            extended="",
            meta="f1e2d3c4b5a69876543210fedcba9876",
            hash="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
            time="2023-01-02T11:00:00Z",
            shared="no",
            toread="yes",
            tags=["science"],
        ),
    ]


def test_save_results_success(fs, sample_bookmarks):
    """
    Tests that save_results correctly saves processed bookmarks to a JSON file
    with tags converted back to space-separated strings.
    """
    output_filepath = "output_bookmarks.json"

    with disable_run_logger():
        save_results.fn(sample_bookmarks, output_filepath)

    assert fs.exists(output_filepath)
    with open(output_filepath, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert len(saved_data) == 2
    assert saved_data[0]["href"] == "http://example.com/page1"
    assert saved_data[0]["extended"] == "A concise summary."
    assert (
        saved_data[0]["tags"] == "tech programming"
    )  # Tags should be space-separated string

    assert saved_data[1]["href"] == "http://example.com/page2"
    assert saved_data[1]["extended"] == ""
    assert saved_data[1]["tags"] == "science"  # Tags should be space-separated string


def test_save_results_empty_list(fs):
    """
    Tests that save_results handles an empty list of bookmarks correctly.
    """
    output_filepath = "empty_output.json"

    with disable_run_logger():
        save_results.fn([], output_filepath)

    assert fs.exists(output_filepath)
    with open(output_filepath, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert saved_data == []
