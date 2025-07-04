import json
from typing import List

from prefect import task

from bookmark_processor.models import Bookmark


@task
def load_bookmarks(filepath: str) -> List[dict]:
    """
    Loads bookmarks from a JSON file.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@task
def save_results(results: List[Bookmark], filepath: str):
    """
    Saves processed bookmarks to a JSON file, ensuring the output schema
    matches the desired input schema format.
    """
    output_data = []

    fields_to_include = {
        "href",
        "description",
        "extended",
        "meta",
        "hash",
        "time",
        "shared",
        "toread",
        "tags",
    }

    for bookmark in results:
        bookmark_dict = bookmark.model_dump(include=fields_to_include)

        if "tags" in bookmark_dict and isinstance(bookmark_dict["tags"], list):
            bookmark_dict["tags"] = " ".join(bookmark_dict["tags"])

        output_data.append(bookmark_dict)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
