====================
CTAO Data Explorer
====================

**Version**:  |version|

A web platform to **search, visualize, and analyze** high‑energy (gamma‑ray) astrophysics data, built with a **React** frontend and a **FastAPI** backend.

- Search by **sky position** and/or **observation time** (TT/UTC/MJD/MET)
- Explore results on an interactive **sky map**, **timeline**, and **energy range** charts
- Sign in with **CTAO IAM** for saved queries, baskets, and job tracking
- **Curate selections** into baskets, then launch **Preview jobs** via OPUS (UWS) for quick‑look analysis

.. currentmodule:: ctao_data_explorer


.. note::

   **Production**: https://padc-ctao-data-explorer.obspm.fr/

----

.. toctree::
   :maxdepth: 1
   :caption: Documentation
   :hidden:

   user-guide/index
   developer-guide/index
   admin/index
   release-notes
   credits

Quick Start
-----------

The recommended local development environment uses a local Kubernetes cluster
— see :doc:`developer-guide/deployment/local`.

Legacy setups directly on host are documented
in :doc:`developer-guide/deployment/legacy`.

For a tour of the UI, see the :doc:`User Guide <user-guide/search>`.
