import json
from typing import List, Dict, Any
from prefect import task
from models import Bookmark

@task
def load_bookmarks(filepath: str) -> List[dict]:
    """
    Loads bookmarks from a JSON file.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

@task
def save_results(results: List[Bookmark], filepath: str):
    """
    Saves processed bookmarks to a JSON file, ensuring the output schema
    matches the desired input schema format.
    """
    output_data = []
    # Define the fields that should be EXPLICITLY INCLUDED in the output JSON.
    # This makes the output schema resilient to new fields added to the Bookmark model.
    fields_to_include = {
        "href",
        "description",
        "extended",
        "meta",
        "hash",
        "time",
        "shared",
        "toread",
        "tags"
    }

    for bookmark in results:
        # Convert Bookmark model to a dictionary, including only the specified fields.
        # Pydantic v2's model_dump() method with the 'include' parameter is used here.
        bookmark_dict = bookmark.model_dump(include=fields_to_include)

        # The 'tags' field is stored internally as a list of strings, but the
        # desired output format is a single space-delimited string.
        # We convert it back here before saving.
        if 'tags' in bookmark_dict and isinstance(bookmark_dict['tags'], list):
            bookmark_dict['tags'] = " ".join(bookmark_dict['tags'])

        output_data.append(bookmark_dict)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
