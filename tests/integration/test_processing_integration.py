import json
from bookmark_processor.tasks.processing import summarize_content, suggest_tags


def test_summarize_content_integration(mock_llm_model):
    """
    Tests that summarize_content formats the prompt correctly and returns the response.
    """
    # Arrange: Use the mock_llm_model fixture
    mock_model, mock_response = mock_llm_model
    # Simulate a realistic LLM output with structured JSON
    mock_response.text.return_value = json.dumps(
        {"summary": "This is a concise summary."}
    )

    input_text = "This is a very long piece of text that needs to be summarized."

    # Act
    result = summarize_content.fn(input_text)

    # Assert
    assert result == "This is a concise summary."

    # Assert that the prompt was called correctly
    mock_model.prompt.assert_called_once()
    call_args, _ = mock_model.prompt.call_args
    prompt_text = call_args[0]
    assert "Please summarize the following content" in prompt_text
    assert input_text in prompt_text


def test_suggest_tags_integration(mock_llm_model):
    """
    Tests that suggest_tags formats the prompt and processes the space-separated response.
    """
    # Arrange: Use the mock_llm_model fixture
    mock_model, mock_response = mock_llm_model
    # Simulate a realistic LLM output with structured JSON
    mock_response.text.return_value = json.dumps(
        {"tags": ["python", "ai", "distributed-systems"]}
    )

    input_text = "Some text about AI and Python."

    # Act
    result = suggest_tags.fn(input_text)

    # Assert: Check that the output is correctly parsed
    assert result == ["python", "ai", "distributed-systems"]

    # Assert that the prompt was called correctly
    mock_model.prompt.assert_called_once()
    call_args, _ = mock_model.prompt.call_args
    prompt_text = call_args[0]
    assert "suggest 3-5 relevant tags" in prompt_text
    assert input_text in prompt_text
