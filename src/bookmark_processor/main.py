from pathlib import Path
from typing import Optional, Set

import typer
from prefect import flow, get_run_logger, task

from bookmark_processor.models import Bookmark, LivenessResult
from bookmark_processor.tasks.io import load_bookmarks, save_results
from bookmark_processor.tasks.liveness import (
    attempt_get_request,
    attempt_headless_browser,
)
from bookmark_processor.tasks.processing import (
    extract_main_content,
    lint_tags,
    load_blessed_tags,
    suggest_tags,
    summarize_content,
)

app = typer.Typer()


def _perform_get_check(url: str) -> Optional[LivenessResult]:
    """Attempts a GET request and returns LivenessResult if successful."""
    logger = get_run_logger()
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
                content=get_result["content"],
            )
    except Exception as e:
        logger.warning(f"GET request failed for {url}: {e}")
    return None


def _perform_headless_check(url: str) -> Optional[LivenessResult]:
    """Attempts a headless browser check and returns LivenessResult if successful."""
    logger = get_run_logger()
    try:
        logger.info(f"Attempting headless browser for {url}")
        headless_result = attempt_headless_browser(url)
        if headless_result:
            logger.info(
                f"Headless browser success for {url}, status: {headless_result['status_code']}"
            )
            return LivenessResult(
                url=url,
                is_live=True,
                status_code=headless_result["status_code"],
                method="HEADLESS",
                final_url=headless_result["final_url"],
                content=headless_result["content"],
            )
    except Exception as e:
        logger.warning(f"Headless browser failed for {url}: {e}")
    return None


@flow(name="Check URL Liveness")
def liveness_flow(url: str) -> LivenessResult:
    """
    Checks the liveness of a given URL using a fallback chain: GET -> Headless.
    """
    logger = get_run_logger()

    # Attempt GET request first
    get_check_result = _perform_get_check(url)
    if get_check_result:
        return get_check_result

    # Attempt headless browser
    headless_check_result = _perform_headless_check(url)
    if headless_check_result:
        return headless_check_result

    logger.error(f"All liveness checks failed for URL: {url}")
    return LivenessResult(
        url=url,
        is_live=False,
        status_code=None,
        method="NONE",
        final_url=None,
        content=None,
    )


def _get_and_extract_content_source(
    bookmark: Bookmark, liveness_result: LivenessResult
) -> Optional[str]:
    """Determines the primary text source for processing (extended, fetched HTML, or direct GET)."""
    logger = get_run_logger()
    text_source = None
    if bookmark.extended:
        text_source = bookmark.extended
        logger.info("Using existing 'extended' description as text source.")
    elif liveness_result.content is not None:  # Changed condition
        logger.info("Extracting main content from fetched HTML via liveness check.")
        text_source = extract_main_content(liveness_result.content)
    else:
        logger.warning(
            f"No content available from liveness check for {bookmark.href}. Attempting direct GET to fetch content."
        )
        try:
            get_result = attempt_get_request(bookmark.href)
            if get_result and get_result["content"] is not None:  # Changed condition
                text_source = extract_main_content(get_result["content"])
                logger.info(f"Direct GET successful for {bookmark.href}.")
            else:
                logger.warning(
                    f"Direct GET failed to retrieve content for {bookmark.href}."
                )
        except Exception as e:
            logger.error(f"Error during direct GET for {bookmark.href}: {e}")
    return text_source


def _summarize_and_update_extended(
    bookmark: Bookmark, text_source: Optional[str]
) -> None:
    """Summarizes content and updates bookmark.extended if conditions are met."""
    logger = get_run_logger()
    if text_source and not bookmark.extended:
        logger.info("Summarizing content for 'extended' description.")
        summary = summarize_content(text_source)
        bookmark.extended = summary


def _suggest_and_add_new_tags(bookmark: Bookmark, text_source: Optional[str]) -> None:
    """Suggests new tags based on content and adds them to the bookmark."""
    logger = get_run_logger()
    if text_source:
        logger.info("Suggesting new tags.")
        new_tags = suggest_tags(text_source)
        all_tags = set(bookmark.tags)
        all_tags.update(new_tags)
        bookmark.tags = sorted(list(all_tags))
        logger.info(f"Added new tags for {bookmark.href}: {new_tags}")


def _lint_and_filter_tags(bookmark: Bookmark, blessed_tags_set: Set[str]) -> None:
    """Lints existing tags and removes unblessed ones."""
    logger = get_run_logger()
    initial_tags = bookmark.tags
    bookmark.tags = lint_tags(bookmark.tags, blessed_tags_set)
    removed_tags = set(initial_tags) - set(bookmark.tags)
    if removed_tags:
        logger.info(f"Removed unblessed tags for {bookmark.href}: {list(removed_tags)}")


@task(name="Process Single Bookmark")
def process_bookmark_flow(bookmark: Bookmark, blessed_tags_set: Set[str]) -> Bookmark:
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
        # Append "data:redirected" tag for bookmarks that were redirected
        bookmark.tags.append("data:redirected")

    if not liveness_result.is_live:
        logger.warning(
            f"Bookmark {bookmark.href} is not live. Skipping content processing."
        )
        # Even if not live, we still want to lint tags and save the bookmark
        # _lint_and_filter_tags(bookmark, blessed_tags_set)  # Passed blessed_tags_set
        # Append "data:offline" tag for bookmarks that failed all liveness checks
        bookmark.tags.append("data:offline")
        return bookmark

    # 2. Determine and extract text source for processing
    # text_source = _get_and_extract_content_source(bookmark, liveness_result)

    # 3. Summarize Content
    # _summarize_and_update_extended(bookmark, text_source)

    # 4. Suggest and add new Tags
    # _suggest_and_add_new_tags(bookmark, text_source)

    # 5. Lint Tags
    # _lint_and_filter_tags(bookmark, blessed_tags_set)

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

    blessed_tags_set = load_blessed_tags("config/blessed_tags.txt")

    # Process each bookmark as a subflow.
    # With ConcurrentTaskRunner, these will run concurrently.
    futures = [
        process_bookmark_flow.submit(bookmark, blessed_tags_set)
        for bookmark in bookmarks
    ]
    results = [f.result() for f in futures]
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
