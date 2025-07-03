# Testing Conventions

This document outlines the conventions for writing tests in this project.

## General Principles

- **Test Framework**: We use `pytest` as our testing framework.
- **Test Location**: Tests are located in the `tests/` directory, mirrored by the `src/` directory structure.
- **Test Types**:
    - **Unit Tests**: Placed in `tests/unit/`. These should test individual functions or classes in isolation.
    - **Integration Tests**: Placed in `tests/integration/`. These test the interaction between multiple components.
- **Test Structure**: Follow the **Arrange-Act-Assert** pattern to structure your tests. Use comments to clearly delineate these sections.

    ```python
    def test_example():
        # Arrange
        ...

        # Act
        ...

        # Assert
        ...
    ```

- **Documentation**: Each test function should have a clear docstring explaining its purpose.

## Mocking

- **General Mocking**: Use the `mocker` fixture from `pytest-mock` for all mocking needs. Avoid direct use of `unittest.mock`.

    ```python
    def test_with_mock(mocker):
        # Arrange
        mock_object = mocker.patch("path.to.object")
        ...
    ```

- **Filesystem**: Use the `fs` fixture from `pyfakefs` to mock the filesystem for tests that involve file I/O.

## Prefect-Specific Testing

- **Testing Tasks**: To test the logic of a Prefect task, call its underlying function using the `.fn` attribute.

    ```python
    from my_module.tasks import my_task

    def test_my_task():
        result = my_task.fn(...)
        assert result == "expected"
    ```

- **Handling Loggers**: If a task uses `get_run_logger()`, wrap the call to its `.fn` method in the `disable_run_logger` context manager to avoid `MissingContextError`.

    ```python
    from prefect.logging import disable_run_logger

    def test_task_with_logger():
        with disable_run_logger():
            result = my_task_with_logger.fn(...)
        ...
    ```

## Parameterization

- Use `@pytest.mark.parametrize` to run the same test with different sets of inputs and expected outputs. This is useful for testing various edge cases with minimal boilerplate.
