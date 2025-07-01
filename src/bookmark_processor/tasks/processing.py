import os
from typing import List, Set
from datetime import timedelta
from prefect import task
from prefect.tasks import task_input_hash

from bs4 import BeautifulSoup
from readability import Document

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough


CACHE_SETTINGS = dict(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=7))


@task
def load_blessed_tags(blessed_tags_path: str = "blessed_tags.txt") -> Set[str]:
    """Loads a set of 'blessed' tags from a text file."""
    try:
        with open(blessed_tags_path, "r", encoding="utf-8") as f:
            tags = {line.strip().lower() for line in f if line.strip()}
        return tags
    except FileNotFoundError:
        print(f"Warning: Blessed tags file not found at {blessed_tags_path}. No tags will be linted.")
        return set()


@task(**CACHE_SETTINGS)
def extract_main_content(html_content: str) -> str:
    """Extracts the main readable content from an HTML string."""
    doc = Document(html_content)
    # Use BeautifulSoup to clean up the readability output if necessary
    soup = BeautifulSoup(doc.content(), "html.parser")
    return soup.get_text(separator="\n", strip=True)


@task
def lint_tags(tags: List[str], blessed_tags: Set[str]) -> List[str]:
    """Filters a list of tags, keeping only those present in the blessed_tags set."""
    if not blessed_tags:
        return tags # If no blessed tags, return all original tags
    return [tag for tag in tags if tag.lower() in blessed_tags]


def get_llm_model():
    """Initializes and returns the LLM model."""
    # Ensure OPENAI_API_KEY is set in your environment
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    return ChatOpenAI(model="gpt-3.5-turbo", temperature=0)


@task(**CACHE_SETTINGS)
def summarize_content(text: str) -> str:
    """Summarizes the given text using an LLM."""
    llm = get_llm_model()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an expert summarizer. Summarize the following text concisely."),
            ("user", "{text}"),
        ]
    )
    chain = {"text": RunnablePassthrough()} | prompt | llm | StrOutputParser()
    return chain.invoke(text)


@task(**CACHE_SETTINGS)
def suggest_tags(text: str) -> List[str]:
    """Suggests relevant tags for the given text using an LLM."""
    llm = get_llm_model()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an expert tag suggester. Suggest 3-5 relevant, comma-separated tags for the following text. Tags should be lowercase and single words or hyphenated compound words (e.g., 'machine-learning')."),
            ("user", "{text}"),
        ]
    )
    chain = {"text": RunnablePassthrough()} | prompt | llm | StrOutputParser()
    raw_tags = chain.invoke(text)
    return [tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()]
