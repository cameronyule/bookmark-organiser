import json
from pathlib import Path
from typing import List

import typer
from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from models import Bookmark, LivenessResult
from tasks.io import save_results
from tasks.liveness import (
    LivenessCheckFailed,
    attempt_get_request,
    attempt_head_request,
    attempt_headless_browser,
)
from tasks.processing import (
    extract_main_content,
    lint_tags,
    summarize_content,
    suggest_tags,
)

app = typer.Typer()


@flow(name="Check URL Liveness")
def liveness_flow(url: str) -> LivenessResult:
    """
    Checks if a URL is live using a fallback chain: HEAD -> GET -> Headless.
    """
    logger = get_run_logger()

    try:
        logger.info(f"Attempting HEAD request for {url}")
        final_url = attempt_head_request(url)
        logger.info(f"HEAD success, final URL: {final_url}. Now attempting GET.")
        get_result = attempt_get_request(final_url)
        return LivenessResult(
            status="success",
            method="head_then_get",
            final_url=get_result["final_url"],
            content=get_result["content"],
        )
    except Exception as e:
        logger.warning(f"HEAD->GET failed for {url}: {e}. Trying GET directly.")

    try:
        logger.info(f"Attempting GET request for {url}")
        get_result = attempt_get_request(url)
        return LivenessResult(
            status="success",
            method="get",
            final_url=get_result["final_url"],
            content=get_result["content"],
        )
    except Exception as e:
        logger.warning(f"GET request failed for {url}: {e}. Trying headless browser.")

    try:
        logger.info(f"Attempting headless browser for {url}")
        headless_result = attempt_headless_browser(url)
        return LivenessResult(
            status="success",
            method="headless",
            final_url=headless_result["final_url"],
            content=headless_result["content"],
        )
    except Exception as e:
        logger.error(f"Headless browser failed for {url}: {e}. All methods failed.")

    raise LivenessCheckFailed(f"All liveness checks failed for URL: {url}")


@flow(name="Process Single Bookmark")
def process_bookmark_flow(bookmark: Bookmark) -> Bookmark:
    """
    Processes a single bookmark: lints tags, checks liveness, and enriches content.
    """
    logger = get_run_logger()
    logger.info(f"Processing bookmark: {bookmark.href}")

    lint_warnings = lint_tags(bookmark.tags)
    for warning in lint_warnings:
        logger.warning(f"Tag linting for {bookmark.href}: {warning}")

    try:
        liveness_result = liveness_flow(bookmark.href)
    except LivenessCheckFailed as e:
        logger.error(str(e))
        if "not-live" not in bookmark.tags:
            bookmark.tags.append("not-live")
        return bookmark

    if bookmark.extended:
        text_source = bookmark.extended
        logger.info("Using existing 'extended' description as text source.")
    else:
        logger.info("Extracting main content from fetched HTML.")
        text_source = extract_main_content(liveness_result.content)

    if not bookmark.extended and text_source:
        logger.info("Summarizing content for 'extended' description.")
        summary = summarize_content(text_source)
        bookmark.extended = summary

    if text_source:
        logger.info("Suggesting new tags.")
        new_tags = suggest_tags(text_source)
        for tag in new_tags:
            if tag not in bookmark.tags:
                bookmark.tags.append(tag)
        logger.info(f"Added new tags for {bookmark.href}: {new_tags}")

    return bookmark


@flow(name="Process All Bookmarks", task_runner=ConcurrentTaskRunner())
def process_all_bookmarks_flow(bookmarks_filepath: str, output_filepath: str):
    """
    Orchestrates the entire bookmark processing pipeline.
    """
    logger = get_run_logger()

    logger.info(f"Reading bookmarks from {bookmarks_filepath}")
    with open(bookmarks_filepath) as f:
        data = json.load(f)
    bookmarks = [Bookmark.model_validate(item) for item in data]
    logger.info(f"Found {len(bookmarks)} bookmarks to process.")

    futures = [process_bookmark_flow.submit(b) for b in bookmarks]
    logger.info(f"Submitted {len(futures)} bookmark processing subflows.")

    results = [future.result() for future in futures]
    logger.info("All subflows completed.")

    logger.info(f"Saving {len(results)} processed bookmarks to {output_filepath}")
    save_results(results, output_filepath)


@app.command()
def run(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="The path to the input JSON file containing the bookmarks.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="The path where the output JSON file will be saved.",
    ),
):
    """
    Process a list of bookmarks to check for liveness, lint tags, and enrich content.
    """
    process_all_bookmarks_flow(str(input_file), str(output_file))


if __name__ == "__main__":
    app()
