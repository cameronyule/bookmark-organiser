import json
from pathlib import Path
from typing import List

import typer
from prefect import flow, get_run_logger
import pendulum # Import pendulum for timezone-aware datetime

from models import Bookmark, LivenessResult
from tasks.io import load_bookmarks, save_results
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
    Checks the liveness of a given URL using a fallback chain: HEAD -> GET -> Headless.
    """
    logger = get_run_logger()

    # Attempt HEAD request first
    try:
        logger.info(f"Attempting HEAD request for {url}")
        head_result = attempt_head_request(url)
        if head_result:
            logger.info(f"HEAD success for {url}, status: {head_result['status_code']}")
            return LivenessResult(
                url=url,
                is_live=True,
                status_code=head_result["status_code"],
                method="HEAD",
                final_url=head_result["final_url"],
                content=None # HEAD request does not return content
            )
    except Exception as e:
        logger.warning(f"HEAD request failed for {url}: {e}")

    # Attempt GET request
    try:
        logger.info(f"Attempting GET request for {url}")
        get_result = attempt_get_request(url)
        if get_result:
            logger.info(f"GET success for {url}, status: {get_result['status_code']}")
            return LivenessResult(
                url=url,
                is_live=True,
                status_code=get_result["status_code"],
                method="GET",
                final_url=get_result["final_url"],
                content=get_result["content"]
            )
    except Exception as e:
        logger.warning(f"GET request failed for {url}: {e}")

    # Attempt headless browser
    try:
        logger.info(f"Attempting headless browser for {url}")
        headless_result = attempt_headless_browser(url)
        if headless_result:
            logger.info(f"Headless browser success for {url}, status: {headless_result['status_code']}")
            return LivenessResult(
                url=url,
                is_live=True,
                status_code=headless_result["status_code"],
                method="HEADLESS",
                final_url=headless_result["final_url"],
                content=headless_result["content"]
            )
    except Exception as e:
        logger.warning(f"Headless browser failed for {url}: {e}")

    logger.error(f"All liveness checks failed for URL: {url}")
    return LivenessResult(url=url, is_live=False, status_code=None, method="NONE", final_url=None, content=None)


@flow(name="Process Single Bookmark")
def process_bookmark_flow(bookmark: Bookmark) -> Bookmark:
    """
    Processes a single bookmark: checks liveness, extracts content, summarizes, and suggests tags.
    """
    logger = get_run_logger()
    logger.info(f"Processing bookmark: {bookmark.href}")

    # 1. Check URL Liveness
    liveness_result = liveness_flow(bookmark.href)

    # Update bookmark href to final URL if redirect occurred
    if liveness_result.final_url and liveness_result.final_url != bookmark.href:
        logger.info(f"URL {bookmark.href} redirected to {liveness_result.final_url}")
        bookmark.href = liveness_result.final_url

    if not liveness_result.is_live:
        logger.warning(f"Bookmark {bookmark.href} is not live. Skipping content processing.")
        # Even if not live, we still want to lint tags and save the bookmark
        initial_tags = bookmark.tags
        bookmark.tags = lint_tags(bookmark.tags) # Lint existing tags
        removed_tags = set(initial_tags) - set(bookmark.tags)
        if removed_tags:
            logger.info(f"Removed unblessed tags for {bookmark.href}: {list(removed_tags)}")
        return bookmark

    # 2. Determine text source for processing
    text_source = None # This variable will hold the extracted content temporarily
    if bookmark.extended:
        text_source = bookmark.extended
        logger.info("Using existing 'extended' description as text source.")
    elif liveness_result.content: # Use content from liveness check if available
        logger.info("Extracting main content from fetched HTML via liveness check.")
        text_source = extract_main_content(liveness_result.content)
    else:
        logger.warning(f"No content available from liveness check for {bookmark.href}. Attempting direct GET to fetch content.")
        # Fallback to direct GET if liveness_result didn't provide content (e.g., HEAD success)
        try:
            get_result = attempt_get_request(bookmark.href)
            if get_result and get_result["content"]:
                text_source = extract_main_content(get_result["content"])
                logger.info(f"Direct GET successful for {bookmark.href}.")
            else:
                logger.warning(f"Direct GET failed to retrieve content for {bookmark.href}.")
        except Exception as e:
            logger.error(f"Error during direct GET for {bookmark.href}: {e}")

    # 3. Summarize Content (only if content exists and no existing extended description)
    if text_source and not bookmark.extended:
        logger.info("Summarizing content for 'extended' description.")
        summary = summarize_content(text_source) # This variable will hold the summary temporarily
        bookmark.extended = summary # Update 'extended' as per original logic

    # 4. Suggest Tags
    if text_source:
        logger.info("Suggesting new tags.")
        new_tags = suggest_tags(text_source)
        # Combine existing tags with suggested tags, ensuring uniqueness
        all_tags = set(bookmark.tags)
        all_tags.update(new_tags)
        bookmark.tags = sorted(list(all_tags))
        logger.info(f"Added new tags for {bookmark.href}: {new_tags}")

    # 5. Lint Tags (using blessed_tags.txt)
    # This will filter tags and return only blessed ones.
    initial_tags = bookmark.tags # Keep a copy to log removed tags
    bookmark.tags = lint_tags(bookmark.tags)
    removed_tags = set(initial_tags) - set(bookmark.tags)
    if removed_tags:
        logger.info(f"Removed unblessed tags for {bookmark.href}: {list(removed_tags)}")


    logger.info(f"Finished processing bookmark: {bookmark.href}")
    return bookmark


@flow(name="Process All Bookmarks")
def process_all_bookmarks_flow(bookmarks_filepath: str, output_filepath: str):
    """
    Orchestrates the entire bookmark processing pipeline.
    """
    logger = get_run_logger()

    logger.info(f"Reading bookmarks from {bookmarks_filepath}")
    data = load_bookmarks(bookmarks_filepath)
    bookmarks = [Bookmark.model_validate(item) for item in data]
    logger.info(f"Found {len(bookmarks)} bookmarks to process.")

    # Process each bookmark as a subflow.
    # With the default SequentialTaskRunner, these will run one after another.
    results = [process_bookmark_flow(b) for b in bookmarks]
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
