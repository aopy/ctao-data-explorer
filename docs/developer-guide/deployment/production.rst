====================
Staging & Production
====================

The application is deployed using a Helm chart
(see `chart/ <https://gitlab.cta-observatory.org/cta-computing/suss/scienceportal/prototypes/ctao-data-explorer/-/blob/master/chart/README.md>`_).

Requirements
=============

- A Kubernetes cluster (tested with standard CNCF-compatible clusters)
- Helm v3
- HAProxy ingress controller

Release and deployment flow
============================

Package release
~~~~~~~~~~~~~~~~

After a package release (see :doc:`/developer-guide/release`), container images
and the Helm chart are built and published to their respective registries.
Images and charts are treated as immutable artifacts.

GitOps-based environment promotion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Production deployments follow GitOps principles managed with **FluxCD**:

1. The application is first deployed to **staging** in the CTAO-SDMC Kubernetes AIV test cluster
2. Charts and images are validated in staging
3. Once validated, the same immutable artifacts are promoted to **pre-production** and **production**

A dedicated Flux Git repository defines the desired state for each environment
(values, secrets, ingress, resources, etc.). Deployment is triggered only by
committing changes to the Flux repository.

This approach ensures:

- Reproducible deployments across environments
- Full traceability of what is running
- Safe and auditable promotion from staging to production
- Clear separation between application release and environment configuration
