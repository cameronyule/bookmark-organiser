import json
from typing import List
from prefect import task
from ..models import Bookmark # Relative import for Bookmark

@task
def load_bookmarks(filepath: str) -> List[dict]:
    """Loads bookmarks from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

@task
def save_results(results: List[Bookmark], filepath: str):
    """Saves processed bookmarks to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([r.model_dump(mode='json') for r in results], f, indent=4, ensure_ascii=False)
