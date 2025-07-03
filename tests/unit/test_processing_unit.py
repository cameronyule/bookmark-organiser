import pytest
from prefect.logging import disable_run_logger

from bookmark_processor.tasks.processing import (
    load_blessed_tags,
    extract_main_content,
    lint_tags,
)

# --- Tests for load_blessed_tags ---


# Using the 'fs' fixture provided by pyfakefs
def test_load_blessed_tags_success(fs):
    """
    Tests that blessed tags are loaded correctly from a valid file.
    """
    # Arrange: Create a fake file in the fake filesystem
    blessed_tags_path = "config/blessed_tags.txt"
    fs.create_file(blessed_tags_path, contents="python\nprefect\nai\n")

    # Act
    with disable_run_logger():
        result = load_blessed_tags.fn(blessed_tags_path)

    # Assert
    assert result == {"python", "prefect", "ai"}


def test_load_blessed_tags_file_not_found(fs):
    """
    Tests that an empty set is returned when the file does not exist.
    """
    # Arrange: The file is not created in the fake filesystem

    # Act
    with disable_run_logger():
        result = load_blessed_tags.fn("non_existent_file.txt")

    # Assert: The function should gracefully return an empty set.
    assert result == set()


def test_load_blessed_tags_with_empty_lines_and_whitespace(fs):
    """
    Tests that blank lines and extra whitespace are correctly handled.
    """
    # Arrange
    blessed_tags_path = "config/blessed_tags.txt"
    fs.create_file(blessed_tags_path, contents="  data-science  \n\n  mlops\n")

    # Act
    with disable_run_logger():
        result = load_blessed_tags.fn(blessed_tags_path)

    # Assert
    assert result == {"data-science", "mlops"}


# --- Tests for extract_main_content ---


@pytest.mark.parametrize(
    "html_input, expected_output",
    [
        # Test 1: Prefers <article> tag
        (
            "<body><header>Header</header><main>Main content</main><article>Article content</article></body>",
            "Article content",
        ),
        # Test 2: Falls back to <main> tag
        (
            "<body><nav>Navbar</nav><main>Main content is here</main><footer>Footer</footer></body>",
            "Main content is here",
        ),
        # Test 3: Falls back to <body> tag
        (
            "<body>Some body text<script>alert(1)</script></body>",
            "Some body text",
        ),
        # Test 4: Handles empty content
        (
            "<html><body></body></html>",
            "",
        ),
        # Test 5: Strips multiple boilerplate tags
        (
            "<body><nav>Nav</nav><div><h1>Title</h1><p>Real text</p></div><style>.a{}</style></body>",
            "Title Real text",
        ),
    ],
)
def test_extract_main_content(html_input, expected_output):
    """
    Tests the main content extraction logic with various HTML structures.
    """
    # Act
    result = extract_main_content.fn(html_input)

    # Assert
    assert result == expected_output


# --- Tests for lint_tags ---


def test_lint_tags_filters_unblessed_tags():
    """
    Tests that tags not in the blessed set are removed.
    """
    # Arrange
    input_tags = ["python", "gossip", "ai", "news"]
    blessed_tags = {"python", "ai", "prefect"}

    # Act
    with disable_run_logger():
        result = lint_tags.fn(input_tags, blessed_tags)

    # Assert: Only the blessed tags should be in the result.
    assert result == ["python", "ai"]


def test_lint_tags_with_no_blessed_tags():
    """
    Tests that if the blessed set is empty, all original tags are returned.
    """
    # Arrange
    input_tags = ["python", "ai"]
    blessed_tags = set()

    # Act
    with disable_run_logger():
        result = lint_tags.fn(input_tags, blessed_tags)

    # Assert: The original list of tags should be returned untouched.
    assert result == ["python", "ai"]


def test_lint_tags_all_tags_are_blessed():
    """
    Tests that no tags are removed if all are in the blessed set.
    """
    # Arrange
    input_tags = ["python", "ai"]
    blessed_tags = {"python", "ai", "prefect"}

    # Act
    with disable_run_logger():
        result = lint_tags.fn(input_tags, blessed_tags)

    # Assert
    assert result == ["python", "ai"]
