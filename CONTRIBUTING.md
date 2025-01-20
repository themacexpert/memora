# Contributing to Memora

We welcome all contributions to Memora! No contribution is too small, even fixing typos. We appreciate your efforts to improve the project.

## Guidelines

- **Docstrings**: Use the Google style for docstrings in your code.

- **Branch Naming**: When creating a new branch for your update, please use descriptive names such as:
  - `feature/...` for new features
  - `bug-fix/...` for bug fixes
  - `typo/...` for typo corrections

- **Testing and Documentation**: Write tests and add documentation for your changes. We use [MkDocs](https://www.mkdocs.org/) for documentation.

- **Package Manager**: We use Poetry as our package manager. Install Poetry by following the instructions [here](https://python-poetry.org/docs/#installation).

  Please DO NOT use pip or conda to install the dependencies. Instead, use Poetry:

  To install all needed packages, run:
  ```
  poetry install
  ```

  To activate the virtual environment, use:
  ```
  poetry shell
  ```

- **Code Style**: Please ensure your code is formatted using [ruff](https://beta.ruff.rs/docs/rules/), [Black](https://black.readthedocs.io/en/stable/), and [isort](https://isort.readthedocs.io/en/latest/). To help with this, we use pre-commit hooks (Note: this is after running `poetry install` and `poetry shell`).

  Make sure to install pre-commit hooks before starting to contribute:
  ```bash
  pre-commit install
  ```

  These hooks will automatically run on your code when you commit changes (`git commit`). If you'd like to run the checks manually on all files before committing, you can run:

  ```bash
  pre-commit run --all-files
  ```

## Process

1. **Fork** the repository.
2. Create a **new branch** with an appropriate name.
3. Make your changes, ensuring they adhere to our style guidelines and are well-documented.
4. **Write tests** for your changes.
5. **Submit a pull request** for review.

We are excited to see your contributions and will be updating the contribution guidelines as the project evolves. Thank you for helping us improve Memora!
