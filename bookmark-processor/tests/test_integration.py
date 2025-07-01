import pytest
import json
from pathlib import Path
from datetime import datetime

# Import the main flow and models from your project
from bookmark_processor import main
from bookmark_processor import models
from bookmark_processor.tasks import processing # Only need processing for mocking load_blessed_tags

# Define a simple blessed_tags content for the test
TEST_BLESSED_TAGS_CONTENT = "tech\nprogramming\nscience\n"

@pytest.fixture
def mock_liveness_result():
    """Fixture to provide a consistent LivenessResult mock."""
    return models.LivenessResult(
        url="https://example.com/mocked", # LivenessResult still uses 'url'
        is_live=True,
        status_code=200,
        response_time=0.1,
        last_checked=datetime.now(),
        check_method="mocked_get"
    )

def test_process_all_bookmarks_flow_integration(tmp_path: Path, mocker, mock_liveness_result):
    """
    Tests the end-to-end processing of bookmarks, mocking external dependencies.
    """
    # 1. Setup: Create temporary input and output files
    input_file = tmp_path / "test_bookmarks_input.json"
    output_file = tmp_path / "test_bookmarks_output.json"
    blessed_tags_file = tmp_path / "blessed_tags.txt" # This file is created but its content is mocked

    # Write the test input bookmarks to a temporary JSON file, matching the full schema
    with open(input_file, "w") as f:
        json.dump(
            [
                {
                    "href": "https://example.com/article1",
                    "description": "Example Article 1",
                    "extended": "This is some initial extended content for article 1.",
                    "meta": "e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
                    "hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                    "time": "2023-01-01T10:00:00Z",
                    "shared": "yes",
                    "toread": "no",
                    "tags": "tech, programming"
                },
                {
                    "href": "https://example.com/article2",
                    "description": "Example Article 2",
                    "extended": "This is some initial extended content for article 2.",
                    "meta": "f1e2d3c4b5a69876543210fedcba9876",
                    "hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
                    "time": "2023-01-02T11:00:00Z",
                    "shared": "no",
                    "toread": "yes",
                    "tags": "science"
                }
            ],
            f,
            indent=2
        )

    # Write dummy blessed tags file (its content will be mocked, but the file needs to exist for path resolution)
    with open(blessed_tags_file, "w") as f:
        f.write(TEST_BLESSED_TAGS_CONTENT)

    # 2. Mock external dependencies and tasks
    # Mock the internal _perform_get_check and _perform_headless_check in main.py
    # These are called by liveness_flow and return LivenessResult
    mocker.patch("bookmark_processor.main._perform_get_check", return_value=mock_liveness_result)
    mocker.patch("bookmark_processor.main._perform_headless_check", return_value=mock_liveness_result)

    # Mock the tasks that interact with external services (e.g., LLM for content extraction, summarization, tag suggestion)
    mocker.patch(
        "bookmark_processor.tasks.processing.extract_main_content",
        side_effect=lambda html: f"Extracted content from {html[:20]}..."
    )
    mocker.patch(
        "bookmark_processor.tasks.processing.summarize_content",
        side_effect=lambda text: f"Summary of: {text[:30]}..."
    )
    mocker.patch(
        "bookmark_processor.tasks.processing.suggest_tags",
        side_effect=lambda text: ["mocked_tag1", "mocked_tag2"] if "article1" in text else ["mocked_tag3"]
    )
    # Mock load_blessed_tags to return a fixed set, regardless of the file path it tries to read
    mocker.patch(
        "bookmark_processor.tasks.processing.load_blessed_tags",
        return_value={"tech", "programming", "science"}
    )

    # 3. Execute the main flow
    # Prefect flows can be called directly as functions for testing.
    # Tasks within the flow will also run locally by default when the flow is called this way.
    main.process_all_bookmarks_flow(
        bookmarks_filepath=str(input_file),
        output_filepath=str(output_file)
    )

    # 4. Assertions
    assert output_file.exists()

    with open(output_file, "r") as f:
        results = json.load(f)

    assert len(results) == 2 # Expecting two processed bookmarks

    # Check the first bookmark's processed data
    bookmark1 = results[0]
    assert bookmark1["href"] == "https://example.com/article1"
    assert bookmark1["description"] == "Example Article 1"
    # These fields are added/updated by the flow
    assert "Extracted content from" in bookmark1["extended_content"]
    assert "Summary of:" in bookmark1["summary"]
    # Verify tags: original blessed tags + new suggested tags
    expected_tags_bookmark1 = {"tech", "programming", "mocked_tag1", "mocked_tag2"}
    assert set(bookmark1["tags"]) == expected_tags_bookmark1
    assert bookmark1["liveness_result"]["is_live"] is True
    assert bookmark1["liveness_result"]["status_code"] == 200
    # Check that original fields are preserved
    assert bookmark1["meta"] == "e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7"
    assert bookmark1["hash"] == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    assert bookmark1["time"] == "2023-01-01T10:00:00Z"
    assert bookmark1["shared"] == "yes"
    assert bookmark1["toread"] == "no"


    # Check the second bookmark's processed data
    bookmark2 = results[1]
    assert bookmark2["href"] == "https://example.com/article2"
    assert bookmark2["description"] == "Example Article 2"
    # These fields are added/updated by the flow
    assert "Extracted content from" in bookmark2["extended_content"]
    assert "Summary of:" in bookmark2["summary"]
    # Verify tags: original blessed tags + new suggested tags
    expected_tags_bookmark2 = {"science", "mocked_tag3"}
    assert set(bookmark2["tags"]) == expected_tags_bookmark2
    assert bookmark2["liveness_result"]["is_live"] is True
    assert bookmark2["liveness_result"]["status_code"] == 200
    # Check that original fields are preserved
    assert bookmark2["meta"] == "f1e2d3c4b5a69876543210fedcba9876"
    assert bookmark2["hash"] == "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"
    assert bookmark2["time"] == "2023-01-02T11:00:00Z"
    assert bookmark2["shared"] == "no"
    assert bookmark2["toread"] == "yes"
