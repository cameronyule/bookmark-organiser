from bookmark_processor.models import Bookmark


def test_bookmark_split_tags_from_string():
    """
    Test that the 'tags' field validator correctly splits a space-separated string into a list.
    """
    bookmark_data = {
        "href": "http://example.com",
        "description": "Test",
        "extended": "",
        "meta": "meta1",
        "hash": "hash1",
        "time": "2023-01-01T00:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "python ai programming",
    }
    bookmark = Bookmark.model_validate(bookmark_data)
    assert bookmark.tags == ["python", "ai", "programming"]


def test_bookmark_split_tags_from_list():
    """
    Test that the 'tags' field validator correctly handles an input that is already a list.
    """
    bookmark_data = {
        "href": "http://example.com",
        "description": "Test",
        "extended": "",
        "meta": "meta1",
        "hash": "hash1",
        "time": "2023-01-01T00:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": ["python", "ai"],
    }
    bookmark = Bookmark.model_validate(bookmark_data)
    assert bookmark.tags == ["python", "ai"]


def test_bookmark_split_tags_empty_string():
    """
    Test that the 'tags' field validator handles an empty string correctly.
    """
    bookmark_data = {
        "href": "http://example.com",
        "description": "Test",
        "extended": "",
        "meta": "meta1",
        "hash": "hash1",
        "time": "2023-01-01T00:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "",
    }
    bookmark = Bookmark.model_validate(bookmark_data)
    assert bookmark.tags == []


def test_bookmark_split_tags_none_input():
    """
    Test that the 'tags' field validator handles None input (should default to empty list).
    """
    bookmark_data = {
        "href": "http://example.com",
        "description": "Test",
        "extended": "",
        "meta": "meta1",
        "hash": "hash1",
        "time": "2023-01-01T00:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": None,  # Pydantic will handle this, default_factory will kick in
    }
    bookmark = Bookmark.model_validate(bookmark_data)
    assert bookmark.tags == []


def test_bookmark_split_tags_whitespace_only_string():
    """
    Test that the 'tags' field validator handles a string with only whitespace.
    """
    bookmark_data = {
        "href": "http://example.com",
        "description": "Test",
        "extended": "",
        "meta": "meta1",
        "hash": "hash1",
        "time": "2023-01-01T00:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "   ",
    }
    bookmark = Bookmark.model_validate(bookmark_data)
    assert bookmark.tags == []
