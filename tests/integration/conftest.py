import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_llm_model(mocker) -> tuple[MagicMock, MagicMock]:
    """
    Mocks the LLM model and its prompt method for integration tests.
    Returns a tuple of (mock_model, mock_response) for flexible assertion and setup.
    """
    mock_response = mocker.MagicMock()
    mock_model = mocker.MagicMock()
    mock_model.prompt.return_value = mock_response

    mocker.patch(
        "bookmark_processor.tasks.processing.get_llm_model", return_value=mock_model
    )
    return mock_model, mock_response
