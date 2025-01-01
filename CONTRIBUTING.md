# Contributing to Memora

We welcome all contributions to Memora! No contribution is too small, even fixing typos. We appreciate your efforts to improve the project.

## Guidelines

- **Code Style**: Please ensure your code is formatted using [Black](https://black.readthedocs.io/en/stable/).

- **Docstrings**: Use the Google style for docstrings in your code.

- **Branch Naming**: When creating a new branch for your update, please use descriptive names such as:
  - `feature/...` for new features
  - `bug-fix/...` for bug fixes
  - `typo/...` for typo corrections

- **Testing and Documentation**: Write tests and add documentation for your changes. We use [MkDocs](https://www.mkdocs.org/) for documentation.

- **Package Manager**: We use Poetry as our package manager. Install Poetry by following the instructions [here](https://python-poetry.org/docs/#installation).

  Please DO NOT use pip or conda to install the dependencies. Instead, use Poetry:

  ```
  make install_all
  ```

  To activate the virtual environment:

  ```
  poetry shell
  ```

## Process

1. **Fork** the repository.
2. Create a **new branch** with an appropriate name.
3. Make your changes, ensuring they adhere to our style guidelines and are well-documented.
4. **Write tests** for your changes.
5. **Submit a pull request** for review.

We are excited to see your contributions and will be updating the contribution guidelines as the project evolves. Thank you for helping us improve Memora!
