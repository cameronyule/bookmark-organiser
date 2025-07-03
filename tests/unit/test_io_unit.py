import json

import pytest
from prefect.logging import disable_run_logger

from bookmark_processor.tasks.io import load_bookmarks, save_results

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
def sample_bookmarks(basic_bookmark):
    """Provides a list of Bookmark objects for testing save_results."""
    bookmark1 = basic_bookmark.model_copy(
        update={
            "href": "http://example.com/page1",
            "description": "Example Page One",
            "extended": "A concise summary.",
            "tags": ["tech", "programming"],
        }
    )
    bookmark2 = basic_bookmark.model_copy(
        update={
            "href": "http://example.com/page2",
            "description": "Example Page Two",
            "extended": "",
            "tags": ["science"],
        }
    )
    return [bookmark1, bookmark2]


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
