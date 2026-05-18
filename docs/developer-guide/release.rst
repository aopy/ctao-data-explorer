===============
Release Process
===============

Versioning follows **Semantic Versioning** (``v<major>.<minor>.<patch>``)
with git tags.

Creating a release
==================

1. **Prepare changelog**

   Collect towncrier fragments into the release notes:

   .. code-block:: bash

       towncrier build --version=<VERSION>

   Commit the updated ``CHANGES.rst`` and remove the fragment files.

2. **Tag the release**

   .. code-block:: bash

       git tag -a v<MAJOR>.<MINOR>.<PATCH> -m "Release v<MAJOR>.<MINOR>.<PATCH>"
       git push origin v<MAJOR>.<MINOR>.<PATCH>

3. **CI publishes automatically**

   On tag push, the pipeline:

   - Builds container images (backend, auth, frontend, playwright)
   - Publishes images to ``harbor.cta-observatory.org/suss/``
   - Packages and publishes the Helm chart
   - Runs all tests and SonarQube analysis

4. **Promote to environments**

   Update the Flux Git repository to reference the new chart version.
   See :doc:`deployment/production` for the promotion flow.

Changelog management
=====================

The project uses ``towncrier``. Each merge request adds a fragment
under ``docs/changes/`` following the naming ``docs/changes/42.bugfix.rst``,
specifying the number of the merge request and the type of change.

Fragment types: ``feature``, ``bugfix``, ``api``, ``optimization``, ``maintenance``.

The need for adding a new fragment in a given merge request can be
omitted if ``no-changelog-needed`` label is added.

See ``pyproject.toml`` for the towncrier configuration.
