from pathlib import Path

from typer.testing import CliRunner

from bookmark_processor.main import app

runner = CliRunner()


def test_cli_run_success(tmp_path: Path, mocker, fs):
    input_file_path = tmp_path / "input.json"
    output_file_path = tmp_path / "output.json"

    fs.create_file(input_file_path)

    mock_process_all_bookmarks_flow = mocker.patch(
        "bookmark_processor.main.process_all_bookmarks_flow"
    )

    result = runner.invoke(
        app,
        [str(input_file_path), str(output_file_path)],
        catch_exceptions=False,
    )

    mock_process_all_bookmarks_flow.assert_called_once_with(
        str(input_file_path), str(output_file_path)
    )

    assert result.exit_code == 0


def test_cli_run_input_file_not_found(tmp_path: Path, mocker):
    input_file_path = tmp_path / "non_existent_input.json"
    output_file_path = tmp_path / "output.json"

    mock_process_all_bookmarks_flow = mocker.patch(
        "bookmark_processor.main.process_all_bookmarks_flow"
    )

    result = runner.invoke(
        app,
        [str(input_file_path), str(output_file_path)],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert " Invalid value for 'INPUT_FILE'" in result.output
    mock_process_all_bookmarks_flow.assert_not_called()


def test_cli_run_missing_arguments(capfd):
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert " Invalid value for 'INPUT_FILE'" in result.output
