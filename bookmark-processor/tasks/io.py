import json
from typing import List

from prefect import task

from models import Bookmark


@task
def load_bookmarks(filepath: str) -> List[dict]:
    """
    Load bookmarks from a JSON file.
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    return data


@task
def save_results(results: List[Bookmark], filepath: str):
    """
    Write the list of processed Bookmark objects to the specified output JSON file,
    overwriting it if it exists.
    """
    with open(filepath, "w") as f:
        json_list = [b.model_dump(mode='json') for b in results] # Use mode='json' for Pydantic v2+
        json.dump(json_list, f, indent=2)

