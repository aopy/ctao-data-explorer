=============================
Development Environment Setup
=============================

This guide describes how to use the aiv-toolkit to deploy a local Kubernetes development environment for the CTAO Data Explorer project.

The local setup closely mirrors staging and production:

- The application runs on Kubernetes (kind cluster)
- Access is provided exclusively via Ingress

Prerequisites
=============

The only required prerequisite is:

- Docker

All other tools required to run the development environment are managed automatically by the aiv-toolkit.

Setting Up the Development Environment
=======================================

Kubernetes development environment can be set up using ``aiv-toolkit``. Internally, it uses ``kind`` to create a local Kubernetes cluster.

Clone the repository:

.. code-block:: bash

    git clone https://gitlab.obspm.fr/oates/ctao-data-explorer.git
    cd ctao-data-explorer
    git submodule update --init --recursive

Start the development environment:

.. code-block:: bash

    make build-dev
    make install-chart

This creates a local Kubernetes cluster using kind and deploys the application using the Helm chart and development values.

Verifying the deployment
=========================

You should be able to see pods running for:

- frontend
- backend
- authentication service
- PostgreSQL
- Redis
- testkit components

For example:

.. code-block:: bash

    $ kubectl get pods
    NAME                                                       READY   STATUS      RESTARTS   AGE
    ctao-data-explorer-7a8c9b4-auth-5ff5c8d67-k2ztf            1/1     Running     0          20h
    ctao-data-explorer-7a8c9b4-backend-78944c48f6-hs2gq        1/1     Running     0          24h
    ctao-data-explorer-7a8c9b4-frontend-cf55bd6f8-8qc4d        1/1     Running     0          2d1h
    ctao-data-explorer-7a8c9b4-postgresql-0                    1/1     Running     0          2d1h
    ctao-data-explorer-7a8c9b4-redis-master-54c8475cf5-bths6   1/1     Running     0          2d1h
    testkit-5498b8cbf6-4hshx                                   1/1     Running     0          2d1h
    toolkit-fluent-bit-g4l56                                   1/1     Running     0          2d1h
    toolkit-wait-for-fluent-bit-z6ps8                          0/1     Completed   0          20h

Accessing the application locally (ingress-based)
===================================================

The development Helm values enable an Ingress by default.
No services are exposed to the host, and port-forwarding is not used.

The ingress hostname is defined in the Helm values:

.. code-block:: yaml

    ingress:
      enabled: true
      className: "haproxy"
      hosts:
        - host: ctao-data-explorer.test.example

Configure local hostname resolution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the following entry to your /etc/hosts file ``127.0.0.1 ctao-data-explorer.test.example``

Open the application
~~~~~~~~~~~~~~~~~~~~

Once the deployment is ready, open your browser at: https://ctao-data-explorer.test.example

Ingress routing is configured as follows:

* ``/api`` → backend
* ``/auth`` → authentication service
* ``/`` → frontend

This is the same routing model used in staging and production environments.

Setting secrets for local development
======================================

Some components (for example authentication or external integrations) require secrets.

How secrets are handled
~~~~~~~~~~~~~~~~~~~~~~~

* Development defaults are provided via Helm values for non-sensitive settings
* Sensitive values must be provided via Kubernetes Secrets
* Secrets are not committed to the repository

Creating or updating secrets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Secrets can be created manually using kubectl, for example:

.. code-block:: bash

    kubectl create secret generic backend-secrets \
      --from-literal=CLIENT_ID=example \
      --from-literal=CLIENT_SECRET=exampleShow

If a secret already exists, update it using:

.. code-block:: bash

    kubectl edit secret backend-secrets

The Helm chart supports consuming secrets via envFrom or secretRef, as defined in the values file.

.. warning::

    Never commit real credentials or secret values to Git.

Accessing a test pod
====================

To start an interactive shell inside a test pod:

.. code-block:: bash

    aiv-deploy helm-dev

This is useful for debugging, inspecting logs, or running commands inside the cluster.

Adding playwright tests
=======================

To add Playwright tests to the project, follow the instructions in the `Playwright documentation <https://playwright.dev/python/docs/codegen>`_.
