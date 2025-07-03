import pytest

from bookmark_processor.models import Bookmark


@pytest.fixture
def basic_bookmark() -> Bookmark:
    """
    Provides a basic Bookmark object with default values for testing.
    Tests can modify this object as needed.
    """
    return Bookmark(
        href="http://example.com/default",
        description="Default Description",
        extended="",
        meta="default_meta",
        hash="default_hash",
        time="2023-01-01T00:00:00Z",
        shared="yes",
        toread="no",
        tags=[],
    )
