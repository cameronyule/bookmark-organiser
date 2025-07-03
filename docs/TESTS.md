# Overall Testing Strategy

The plan is to separate tests into two categories: Unit Tests and Integration Tests. This separation ensures that we can test different aspects of the code effectively.

Unit Tests: These will form the majority of our tests. They will test each function (task) in complete isolation. All external dependencies—such as the filesystem (open) and the LLM library (llm)—will be "mocked" or faked.

Rationale: Unit tests are fast, deterministic, and reliable. By isolating a function, we can verify its internal logic without worrying about external systems. If a unit test fails, we know the bug is within that specific function, which makes debugging much easier.

Integration Tests: These tests will verify the interactions between our code and its immediate, direct dependencies. In this case, the most critical integration point is the connection to the llm library.

Rationale: While unit tests confirm our logic is correct, they don't confirm that we are using external libraries correctly. These tests will mock the LLM API call itself but will test that our code (e.g., summarize_content) correctly calls the llm library with the expected prompt format and correctly processes its response. This gives us confidence that our code "integrates" properly with the external tool.

## Required Libraries

To implement this plan, you will need to add the following libraries to your development dependencies:

```sh
pip install pytest pytest-mock pyfakefs
```

pytest: The testing framework.

pytest-mock: Provides a simple fixture (mocker) for patching objects and mocking dependencies.

pyfakefs: A fantastic library that lets us create a fake in-memory filesystem for testing file I/O without touching the actual disk.

## Suggested File Structure

A standard and clean way to organize your tests is as follows:

```
your_project/
├── src/bookmark_processor/
│   └── tasks/
│       └── processing.py # The file you provided
├── config/
│   └── blessed_tags.txt
└── tests/
    ├── __init__.py
    ├── conftest.py       # Optional: for shared fixtures
    ├── unit/
    │   ├── __init__.py
    │   └── test_processing_unit.py
    └── integration/
        ├── __init__.py
        └── test_processing_integration.py
```

## Detailed Testing Plan & Examples

Here is a breakdown of the tests for each function.

1. `load_blessed_tags`

This function's main dependency is the filesystem. We will use pyfakefs to create virtual files for our tests.

Rationale: Using pyfakefs is superior to mocking the built-in open function because it correctly simulates a real filesystem environment. This allows us to test file paths, FileNotFoundError, and file content in a very realistic way without writing/deleting actual files on disk.

2. `extract_main_content`

This is a pure function that depends only on its input and BeautifulSoup. No mocking is needed. We can test it by providing different HTML snippets. pytest.mark.parametrize is perfect for this.

Rationale: We want to test the fallback logic: <article> -> <main> -> <body>. We also need to confirm that boilerplate tags (<nav>, <script>, etc.) are removed.

3. `lint_tags`

This is another pure function. We need to test its filtering logic.

4. `summarize_content` & `suggest_tags`

These tasks interact with an external service (llm). Directly calling this service in tests is slow, expensive, and non-deterministic. We will use pytest-mock to replace get_llm_model with a fake "mock" object.

Rationale: This is our integration test. We are not testing the LLM's ability to summarize; we are testing that our code correctly:

Calls the llm library.

Builds the correct prompt string.

Processes the library's response.
