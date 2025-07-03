import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from prefect.testing.utilities import prefect_test_harness
from bookmark_processor.main import app

runner = CliRunner()


@pytest.fixture(autouse=True, scope="module")
def prefect_test_fixture():
    """
    Fixture to run tests within a Prefect test harness.
    """
    with prefect_test_harness():
        yield


def test_cli_run_success(tmp_path: Path, mocker, fs):
    """
    Tests that the CLI 'run' command successfully invokes the main flow
    and handles file paths correctly.
    """
    input_file_path = tmp_path / "input.json"
    output_file_path = tmp_path / "output.json"

    # Create a dummy input file in the fake filesystem
    dummy_input_content = [
        {
            "href": "http://example.com/page1",
            "description": "Example Page One",
            "extended": "",
            "meta": "e6a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
            "hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "time": "2023-01-01T10:00:00Z",
            "shared": "yes",
            "toread": "no",
            "tags": "tech programming",
        }
    ]
    fs.create_file(input_file_path, contents=json.dumps(dummy_input_content))

    # Mock the actual Prefect flow to prevent it from running fully
    # and to verify it's called with correct arguments.
    mock_process_all_bookmarks_flow = mocker.patch(
        "bookmark_processor.main.process_all_bookmarks_flow"
    )

    # Act
    result = runner.invoke(
        app,
        ["run", str(input_file_path), str(output_file_path)],
    )

    # Assert
    assert result.exit_code == 0
    mock_process_all_bookmarks_flow.assert_called_once_with(
        str(input_file_path), str(output_file_path)
    )
    assert (
        "Processing all bookmarks flow completed." in result.stdout
    )  # Check for a message from the flow if it were to run, or just general success.
    # Note: The actual output file won't be created by the mocked flow,
    # so we don't assert its existence here.


def test_cli_run_input_file_not_found(tmp_path: Path, mocker):
    """
    Tests that the CLI 'run' command exits with an error if the input file does not exist.
    """
    input_file_path = tmp_path / "non_existent_input.json"
    output_file_path = tmp_path / "output.json"

    # Mock the flow to ensure it's not called if input file check fails
    mock_process_all_bookmarks_flow = mocker.patch(
        "bookmark_processor.main.process_all_bookmarks_flow"
    )

    # Act
    result = runner.invoke(
        app,
        ["run", str(input_file_path), str(output_file_path)],
    )

    # Assert
    assert result.exit_code != 0  # Should exit with an error
    assert "Path 'non_existent_input.json' does not exist." in result.stderr
    mock_process_all_bookmarks_flow.assert_not_called()


def test_cli_run_missing_arguments():
    """
    Tests that the CLI 'run' command requires both input and output file paths.
    """
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    assert "Missing argument 'INPUT_FILE'." in result.stderr
    assert "Missing argument 'OUTPUT_FILE'." in result.stderr
