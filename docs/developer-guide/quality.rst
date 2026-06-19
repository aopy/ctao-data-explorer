=================
Quality Assurance
=================

This page describes the quality assurance measures enforced in the CI/CD
pipeline. For instructions on running these checks locally, see
:doc:`developer-workflow`.

Overview
========

Every merge request goes through the following QA jobs:

+---------------------------+--------------------------------------+
| Job                       | What it enforces                     |
+===========================+======================================+
| ``pylint``                | Python static analysis (score ≥ 5.0) |
+---------------------------+--------------------------------------+
| ``pre-commit-hooks``      | Ruff lint/format, mypy, YAML/JSON    |
+---------------------------+--------------------------------------+
| ``hadolint``              | Dockerfile best practices            |
+---------------------------+--------------------------------------+
| ``kube-lint``             | Security-focused k8s manifest lint   |
+---------------------------+--------------------------------------+
| ``kubeconform``           | Kubernetes manifest schema validation|
+---------------------------+--------------------------------------+
| ``kube-score``            | Kubernetes best practice scoring     |
+---------------------------+--------------------------------------+
| ``unit-tests-backend``    | Python unit tests + coverage         |
+---------------------------+--------------------------------------+
| ``unit-tests-frontend``   | JavaScript unit tests + coverage     |
+---------------------------+--------------------------------------+
| ``k8s-integration-tests`` | Playwright E2E on k8s cluster        |
+---------------------------+--------------------------------------+
| ``sonarqube``             | Quality gate, coverage, security     |
+---------------------------+--------------------------------------+

Linting & formatting
=====================

Python code is checked with **Ruff** (linting and formatting) and **mypy**
(type checking). These are run via ``prek`` pre-commit hook manager.
Configuration is in ``.pre-commit-config.yaml`` and ``pyproject.toml``.

Unit tests
===========

- **Python**: ``pytest`` with async support. Test files are in ``api/tests/``
  and ``auth_service/tests/``.
- **Frontend**: Jest (via CRA/Craco). Tests live alongside components are in
  ``js/src/``.

In both cases coverage reports are generated and uploaded to SonarQube for
further analysis.

E2E integration tests
======================

Playwright tests run against a full deployment on a kind cluster, verifying
critical user flows end-to-end.

SonarQube analysis
===================

The SonarQube scanner analyses the full codebase (Python + JavaScript) after
all tests have run. It checks:

- Code coverage (Python and JavaScript)
- Reliability and maintainability issues: code smells, bugs and vulnerabilities
- Security hotspots
- A **quality gate** must pass before the MR can be merged
