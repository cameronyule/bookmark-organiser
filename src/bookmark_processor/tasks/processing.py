import json
from datetime import timedelta
from typing import List, Set

import llm
from bs4 import BeautifulSoup
from prefect import task
from prefect.tasks import task_input_hash

from bookmark_processor.models import SuggestedSummary, SuggestedTags

CACHE_SETTINGS = dict(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))


@task
def load_blessed_tags(blessed_tags_path: str = "config/blessed_tags.txt") -> Set[str]:
    """
    Loads the set of blessed tags from a file.
    """
    from prefect import get_run_logger

    logger = get_run_logger()
    try:
        with open(blessed_tags_path) as f:
            blessed_tags = {line.strip() for line in f if line.strip()}
        logger.info(f"Loaded {len(blessed_tags)} blessed tags from {blessed_tags_path}")
        return blessed_tags
    except FileNotFoundError:
        logger.warning(
            f"Could not find blessed tags file at: {blessed_tags_path}. Tag linting will not be performed."
        )
        return set()  # Return an empty set if file not found


@task(**CACHE_SETTINGS)
def extract_main_content(html_content: str) -> str:
    """
    Use BeautifulSoup to parse HTML and implement logic to extract the core article text,
    stripping out boilerplate like navbars, ads, and footers.
    """
    soup = BeautifulSoup(html_content, "lxml")
    for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
        script_or_style.decompose()

    article = soup.find("article")
    if article:
        return article.get_text(separator=" ", strip=True)

    main_content = soup.find("main")
    if main_content:
        return main_content.get_text(separator=" ", strip=True)

    if soup.body:
        return soup.body.get_text(separator=" ", strip=True)

    return ""


@task
def lint_tags(tags: List[str], blessed_tags: Set[str]) -> List[str]:
    """
    Compare input tags against a "blessed" set.
    Return a list of tags that are in the blessed set.
    Log warnings for tags that are not in the set.
    """
    from prefect import get_run_logger

    logger = get_run_logger()

    if not blessed_tags:
        logger.warning("No blessed tags provided. No tag linting performed.")
        return tags  # Return original tags if no blessed tags are available

    linted_tags = []
    for tag in tags:
        if tag in blessed_tags:
            linted_tags.append(tag)
        else:
            logger.warning(
                f"Tag '{tag}' is not in the blessed list and will be removed."
            )
    return linted_tags


def get_llm_model():
    """Gets the LLM model. Assumes `llm` is configured."""
    return llm.get_model("qwen3:8b")


@task(**CACHE_SETTINGS)
def summarize_content(text: str) -> str:
    """
    Call the LLM API (via llm library) with the text to generate a summary.
    """
    model = get_llm_model()

    prompt = (
        "Please summarize the following content in one or two concise sentences."
        "Do not output anything other than the summarisation."
        "\n\n"
        f"{text}"
    )

    response = model.prompt(prompt, schema=SuggestedSummary)
    response_json = json.loads(response.text())
    return response_json["summary"]


@task(**CACHE_SETTINGS)
def suggest_tags(text: str) -> List[str]:
    """
    Call the LLM API (via llm library) to suggest relevant tags.
    """
    model = get_llm_model()

    prompt = (
        "Based on the following text, suggest 3-5 relevant tags as a single "
        "space-separated line. Use lowercase and no numbers. Prefer single "
        "words but use '-' as a delimiter for multiple words if needed."
        "Output only the suggested tags, nothing else."
        "Example: python programming distributed-systems ai\n\n"
        f"{text}"
    )

    response = model.prompt(prompt, schema=SuggestedTags)
    response_json = json.loads(response.text())
    return response_json["tags"]
