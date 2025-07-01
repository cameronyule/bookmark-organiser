import json
from typing import List

from prefect import task

from models import Bookmark


@task
def save_results(results: List[Bookmark], filepath: str):
    """
    Write the list of processed Bookmark objects to the specified output JSON file,
    overwriting it if it exists.
    """
    with open(filepath, "w") as f:
        json_list = [b.model_dump() for b in results]
        json.dump(json_list, f, indent=2)
