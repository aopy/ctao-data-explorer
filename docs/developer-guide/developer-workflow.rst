===================
Developer Workflow
===================

How to run all quality checks locally before pushing. These same checks
are enforced in CI (see :doc:`quality`).

Pre-commit hooks
=================

.. code-block:: bash

    uv sync --locked --extra all
    uv run prek run --all-files

Run on a single file:

.. code-block:: bash

    uv run prek run --files path/to/file.py

Checks include: Ruff lint/format, mypy types, YAML/JSON validation.

Python tests
=============

.. code-block:: bash

    uv sync --locked --extra test
    uv run pytest

    # With coverage
    uv run pytest --cov=api --cov=auth_service --cov-report=term-missing

    # Run a specific file
    uv run pytest api/tests/test_csrf.py

    # Run matching tests
    uv run pytest -k "test_query"

Frontend tests
===============

.. code-block:: bash

    cd js
    npm ci
    npm test -- --watchAll=false --coverage

E2E tests with Playwright
==========================

Playwright tests are defined in ``tests/test_playwright.py`` at the project root.

Integration tests run against a full deployment in the kind cluster.
See :doc:`deployment/local` for cluster setup, then run:

.. code-block:: bash

    pytest tests/test_playwright.py

To add or debug tests, use the Playwright code generator or follow the
`Playwright documentation <https://playwright.dev/python/docs/codegen>`_.

Building documentation locally
===============================

.. code-block:: bash

    uv sync --locked --extra doc
    uv run sphinx-build -W --keep-going -n docs docs/build/html

Or using the docs Makefile:

.. code-block:: bash

    make -C docs html

The output is written to ``docs/build/html/``.
Configuration is in ``docs/conf.py``.
