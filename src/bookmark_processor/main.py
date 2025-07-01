import sys
from pathlib import Path
from typing import Optional, Set

import typer
from prefect import flow, task
from prefect.tasks import task_input_hash
from prefect_selenium import SeleniumWebDriver
from prefect_selenium.tasks import open_webpage, get_page_content

from .models import Bookmark, LivenessResult
from .tasks.io import load_bookmarks, save_results
from .tasks.liveness import attempt_get_request, attempt_headless_browser
from .tasks.processing import (
    load_blessed_tags,
    extract_main_content,
    lint_tags,
    summarize_content,
    suggest_tags,
)

app = typer.Typer()


def _perform_get_check(url: str) -> Optional[LivenessResult]:
    """Performs a GET request check for URL liveness."""
    try:
        response_data = attempt_get_request.submit(url).result()
        if response_data:
            return LivenessResult(
                is_live=True,
                status_code=response_data.get("status_code"),
                content_type=response_data.get("content_type"),
                html_content=response_data.get("html_content"),
                error_message=None,
                check_method="GET",
            )
    except Exception as e:
        return LivenessResult(
            is_live=False,
            status_code=None,
            content_type=None,
            html_content=None,
            error_message=str(e),
            check_method="GET",
        )
    return None


def _perform_headless_check(url: str) -> Optional[LivenessResult]:
    """Performs a headless browser check for URL liveness."""
    try:
        with SeleniumWebDriver(browser="chrome") as driver:
            open_webpage.submit(driver, url).result()
            html_content = get_page_content.submit(driver).result()
            if html_content:
                return LivenessResult(
                    is_live=True,
                    status_code=200,  # Assume 200 if content is retrieved
                    content_type="text/html",
                    html_content=html_content,
                    error_message=None,
                    check_method="HEADLESS",
                )
    except Exception as e:
        return LivenessResult(
            is_live=False,
            status_code=None,
            content_type=None,
            html_content=None,
            error_message=str(e),
            check_method="HEADLESS",
        )
    return None


@flow(name="Check URL Liveness")
def liveness_flow(url: str) -> LivenessResult:
    """
    Checks the liveness of a URL, first with a GET request, then with a headless browser if needed.
    """
    typer.echo(f"Checking liveness for: {url}")
    get_result = _perform_get_check(url)
    if get_result and get_result.is_live:
        typer.echo(f"  GET check successful (Status: {get_result.status_code})")
        return get_result

    typer.echo("  GET check failed or inconclusive, attempting headless browser...")
    headless_result = _perform_headless_check(url)
    if headless_result and headless_result.is_live:
        typer.echo("  Headless browser check successful.")
        return headless_result

    typer.echo("  Both liveness checks failed.")
    return headless_result or get_result or LivenessResult(is_live=False, error_message="All liveness checks failed.")


def _get_and_extract_content_source(bookmark: Bookmark, liveness_result: LivenessResult) -> Optional[str]:
    """
    Extracts the main content from the liveness result's HTML content.
    """
    if liveness_result and liveness_result.is_live and liveness_result.html_content:
        typer.echo(f"  Extracting main content for {bookmark.url}...")
        return extract_main_content.submit(liveness_result.html_content).result()
    return None


def _summarize_and_update_extended(bookmark: Bookmark, text_source: Optional[str]) -> None:
    """
    Summarizes the content and updates the bookmark's extended_description.
    """
    if text_source:
        typer.echo(f"  Summarizing content for {bookmark.url}...")
        summary = summarize_content.submit(text_source).result()
        if summary:
            bookmark.extended_description = summary
            typer.echo("  Extended description updated.")
        else:
            typer.echo("  Failed to generate summary.")


def _suggest_and_add_new_tags(bookmark: Bookmark, text_source: Optional[str]) -> None:
    """
    Suggests new tags based on content and adds them to the bookmark.
    """
    if text_source:
        typer.echo(f"  Suggesting new tags for {bookmark.url}...")
        suggested_tags = suggest_tags.submit(text_source).result()
        if suggested_tags:
            # Add suggested tags, avoiding duplicates
            current_tags_set = set(bookmark.tags)
            new_tags_added = False
            for tag in suggested_tags:
                if tag not in current_tags_set:
                    bookmark.tags.append(tag)
                    current_tags_set.add(tag)
                    new_tags_added = True
            if new_tags_added:
                typer.echo(f"  Added new tags: {', '.join(suggested_tags)}")
            else:
                typer.echo("  No new tags suggested or all already present.")
        else:
            typer.echo("  Failed to suggest tags.")


def _lint_and_filter_tags(bookmark: Bookmark, blessed_tags_set: Set[str]) -> None:
    """
    Lints and filters tags based on a blessed list.
    """
    if blessed_tags_set:
        original_tags = set(bookmark.tags)
        typer.echo(f"  Linting tags for {bookmark.url}...")
        linted_tags = lint_tags.submit(bookmark.tags, blessed_tags_set).result()
        bookmark.tags = linted_tags
        removed_tags = original_tags - set(linted_tags)
        if removed_tags:
            typer.echo(f"  Removed unblessed tags: {', '.join(removed_tags)}")
        else:
            typer.echo("  No unblessed tags found.")
    else:
        typer.echo("  No blessed tags provided for linting.")


@flow(name="Process Single Bookmark")
def process_bookmark_flow(bookmark: Bookmark, blessed_tags_set: Set[str]) -> Bookmark:
    """
    Processes a single bookmark: checks liveness, extracts content, summarizes,
    suggests tags, and lints tags.
    """
    typer.echo(f"\nProcessing bookmark: {bookmark.title} ({bookmark.url})")

    # 1. Check URL Liveness
    liveness_result = liveness_flow(bookmark.url)
    bookmark.liveness = liveness_result

    if not liveness_result.is_live:
        typer.echo(f"  Bookmark {bookmark.url} is not live. Skipping content processing.")
        return bookmark

    # 2. Get and Extract Content Source
    text_source = _get_and_extract_content_source(bookmark, liveness_result)

    # 3. Summarize and Update Extended Description
    _summarize_and_update_extended(bookmark, text_source)

    # 4. Suggest and Add New Tags
    _suggest_and_add_new_tags(bookmark, text_source)

    # 5. Lint and Filter Tags
    _lint_and_filter_tags(bookmark, blessed_tags_set)

    typer.echo(f"Finished processing bookmark: {bookmark.title}")
    return bookmark


@flow(name="Process All Bookmarks")
def process_all_bookmarks_flow(bookmarks_filepath: str, output_filepath: str):
    """
    Main flow to load, process, and save bookmarks.
    """
    typer.echo(f"Loading bookmarks from {bookmarks_filepath}...")
    bookmarks_data = load_bookmarks.submit(bookmarks_filepath).result()
    bookmarks = [Bookmark(**data) for data in bookmarks_data]
    typer.echo(f"Loaded {len(bookmarks)} bookmarks.")

    typer.echo("Loading blessed tags...")
    blessed_tags_set = load_blessed_tags.submit().result()
    typer.echo(f"Loaded {len(blessed_tags_set)} blessed tags.")

    processed_bookmarks = []
    for bookmark in bookmarks:
        processed_bookmark = process_bookmark_flow(bookmark, blessed_tags_set)
        processed_bookmarks.append(processed_bookmark)

    typer.echo(f"\nSaving processed bookmarks to {output_filepath}...")
    save_results.submit(processed_bookmarks, output_filepath).result()
    typer.echo("Processing complete!")


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
        "processed_bookmarks.json",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="The path to save the processed bookmarks JSON file.",
    ),
):
    """
    Runs the bookmark processing flow.
    """
    typer.echo("Starting bookmark processing...")
    process_all_bookmarks_flow(str(input_file), str(output_file))
    typer.echo("Bookmark processing finished.")


if __name__ == "__main__":
    app()
