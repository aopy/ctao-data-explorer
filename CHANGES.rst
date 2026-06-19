v0.9.0 – 2025-11-14
===================

Added
-----

- Basic Prometheus metrics in the backend, with hook points and Redis instrumentation for monitoring TAP and OPUS activity. (`b96f2bd <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b96f2bd>`_ `ef61bf9 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ef61bf9>`_ `c8a05fa <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c8a05fa>`_)
- Fixed header with CTAO SVG logo and sticky sub-navigation for the main tabs. (`92fbbcb <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/92fbbcb>`_ `e24cc79 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e24cc79>`_ `3d1ee9e <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3d1ee9e>`_)
- Pytest coverage for backend endpoints, authentication, baskets, query history, OPUS integration, and logging/metrics. (`24a8e90 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/24a8e90>`_ `7448478 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7448478>`_ `e7a7da3 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e7a7da3>`_ `83ef003 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/83ef003>`_)
- GitLab Pages documentation and updated README describing deployment and usage. (`6e7fcf0 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6e7fcf0>`_ `27dd9d4 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/27dd9d4>`_ `45688e2 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/45688e2>`_ `db73b32 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/db73b32>`_ `466ddb4 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/466ddb4>`_)

Changed
-------

- Improved wording in the search form (epoch). (`9707309 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9707309>`_)
- Updated instance-runner configuration and CI jobs to stabilise Pages builds. (`886c6ca <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/886c6ca>`_ `7a7031e <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7a7031e>`_)

Fixed
-----

- Corrected metrics for OPUS jobs and avoided double-counting job outcomes. (`3a1c1f4 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3a1c1f4>`_ `b7eb499 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b7eb499>`_)
- Fixed preview-job list refresh after Preview / OPUS actions. (`57986c2 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/57986c2>`_)
- Fixed minor style and content issues in README and documentation. (`f390a7a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f390a7a>`_ `466ddb4 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/466ddb4>`_)


v0.8.0 – 2025-10-08
===================

Added
-----

- **OPUS integration:** job-list tab, quick-look analysis, and per-job *Preview* button. (`47a13164 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/47a13164>`_ `d0f6e63a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d0f6e63a>`_ `505f2933 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/505f2933>`_)

Changed
-------

- Use **application token** instead of user token when querying OPUS. (`c52362b1 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c52362b1>`_)
- Refactor: move constants/defaults to ``constants.py`` and ``config.py``. (`dd01094e <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/dd01094e>`_)
- Replace ``print`` with structured logging. (`150c61fa <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/150c61fa>`_)
- Deduplicate ADQL queries and tighten query logic. (`63db6c1a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/63db6c1a>`_)
- Remove separate "MET" time-system row; integrate MET fields into Start/End rows with fixed epoch. (`2d9fb6cb <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/2d9fb6cb>`_)
- Search form: Time system and scale option for the MJD fields. (`87f3af13 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/87f3af13>`_)

Fixed
-----

- Design issues in job-detail page and broken job-list fetch from OPUS. (`e4fe90ef <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e4fe90ef>`_ `c80f8b39 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c80f8b39>`_)

Removed
-------

- Local browser storage of jobs. (`80037df3 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/80037df3>`_)
- References to deprecated ``gammapy_maps`` service. (`6078fced <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6078fced>`_)


v0.7.0 – 2025-08-07
===================

Added
-----

- **MET time-system support** in search form; MET fields now persist across login. (`ec6dc47b <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ec6dc47b>`_ `8d67b024 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8d67b024>`_)
- Unified **TT / UTC** time-system menu. (`d72d8bb8 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d72d8bb8>`_)
- Toggle and grouped coordinate/time buttons. (`62e8a146 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/62e8a146>`_)
- Multi-item selection in maps and charts; bulk *Add to Basket*. (`61b837e2 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/61b837e2>`_)
- Default column set and column-toggle improvements in results table. (`1e1c25aa <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1e1c25aa>`_ `29eb58f8 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/29eb58f8>`_)

Changed
-------

- Date fields switched to **YYYY-MM-DD**; MJD labels indicate TT / UTC. (`6d5ca1da <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6d5ca1da>`_)
- Documentation and changelog updates. (`d997c7f2 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d997c7f2>`_)

Fixed
-----

- Time-shift error in Basket tab. (`f1014ea0 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f1014ea0>`_)
- Timeline chart TT issue. (`a95f485f <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a95f485f>`_)

Removed
-------

- Obsolete **ADQL-hash** feature. (`4e1fde43 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/4e1fde43>`_)


v0.6.0 – 2025-07-08
====================

Added
-----

- Cache search results in Redis (1 h) to speed up repeat queries. (`136fe8a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/136fe8a>`_)
- Simbad/NED dropdown auto-suggestions with Redis-backed caching. (`7c8fe93 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7c8fe93>`_)
- Bidirectional selection sync between results table, sky map & charts. (`063d61b <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/063d61b>`_)
- Column descriptions in config; show as tooltips. (`ca149af <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ca149af>`_)
- Basket UX: add items to multiple baskets; duplicate baskets; provide a default basket. (`5cfc83f <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/5cfc83f>`_)
- Temporarily store user info (name/email) in Redis; display in profile tab, stop storing user name & email in DB. (`877d952 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/877d952>`_)
- **Documentation:** initial CHANGELOG draft. (`27e7f6f <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/27e7f6f>`_)

Changed
-------

- Object lookup: resolve objects in NED catalogue via ``ObjectLookup``; improves object suggestions. (`f9848fc <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f9848fc>`_)
- UI: improve chart & sky map design; adopt Okabe–Ito colour-blind–safe palette. (`e103af8 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e103af8>`_)
- Use standard names for columns in config. (`0bd8b89 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0bd8b89>`_)
- Temporarily disable ``https_only`` in middleware (deployment workaround). (`b46fdfa <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b46fdfa>`_)

Fixed
-----

- Refresh-token handling. (`f3df089 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f3df089>`_)
- Object suggestion edge cases. (`b010739 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b010739>`_)
- Production callback URL. (`7e6ccdd <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7e6ccdd>`_)
- Time search issue. (`dec5eca <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/dec5eca>`_)


v0.5.0 – 2025-06-06
====================

Added
-----

- Introduce FastAPI BFF service for auth: store encrypted refresh tokens in the DB and session IDs in Redis. (`c1db462 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c1db462>`_)

Changed
-------

- Switch to ``date-fns-tz`` for timezone formatting. (`51cc2a7 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/51cc2a7>`_)

Fixed
-----

- Timeline chart time formatting (locale). (`095c695 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/095c695>`_)
- Electromagnetic-range chart min/max energy swap. (`336a054 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/336a054>`_)
- Query Store summary coordinate/date bug. (`87f5eb1 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/87f5eb1>`_)


v0.4.0 – 2025-04-25
====================

Added
-----

- Query Store: persist user queries & results in DB; history tab; store ADQL query hash for (future) caching. (`2fa35db <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/2fa35db>`_)

Changed
-------

- Search form redesigned; add MJD & equatorial HMS/DMS inputs. (`29b7f05 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/29b7f05>`_)
- Improve basket-group structure; allow items in multiple baskets. (`9898f15 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9898f15>`_)
- Use Astropy Table instead of TAPResults for TAP queries. (`01a6827 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01a6827>`_)
- Simplify Aladin Lite component; single catalogue. (`9455c4a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9455c4a>`_)
- Expose API endpoint to fetch basket groups by ID. (`f046f4d <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f046f4d>`_)
- Cookie-based authentication. (`6ddcb87 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6ddcb87>`_)

Removed
-------

- Drop FastAPI Users login endpoint (only CTAO IAM login used). (`978e728 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/978e728>`_)

Fixed
-----

- Build DataLink URL from incoming request. (`c9df34a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c9df34a>`_)


v0.3.0 – 2025-03-13
====================

Added
-----

- Record user search history and show it in the user-profile modal. (`434ebd0 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/434ebd0>`_)
- Observation time-interval search. (`ea13edc <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ea13edc>`_)
- DataLink support. (`605b2eb <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/605b2eb>`_)
- Basket functionality. (`01e6001 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01e6001>`_)
- Modal view of items in the basket tab. (`8a71379 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8a71379>`_)
- User first name in header. (`3a753c0 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3a753c0>`_)

Changed
-------

- Multiple basket groups. (`40c310a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/40c310a>`_)

Fixed
-----

- Disappearing basket groups. (`d1b5fb7 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d1b5fb7>`_)


v0.2.0 – 2025-01-27
====================

Added
-----

- OpenID Connect authentication (FastAPI Users + Authlib). (`1f6727a <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1f6727a>`_)
- Support galactic coordinate system input. (`721fc3e <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/721fc3e>`_)
- Object resolve via NED. (`0a23005 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0a23005>`_)
- Object resolve via Simbad. (`6c349dc <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6c349dc>`_)
- Bootstrap UI. (`d157455 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d157455>`_)
- Download button in results table. (`4346006 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/4346006>`_)

Changed
-------

- Use TeV in EM chart. (`a7fc6b0 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a7fc6b0>`_)
- Aladin Lite v3. (`0aff94d <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0aff94d>`_)

Fixed
-----

- Zooming issue in timeline chart. (`52c705f <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/52c705f>`_)


v0.1.0 – 2024-12-06
====================

Added
-----

- Electromagnetic-range chart using Plotly. (`3529438 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3529438>`_)
- Timeline chart using Plotly. (`a2f227c <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a2f227c>`_)
- React front-end. (`e053314 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e053314>`_)
- FastAPI back-end foundation. (`05be991 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/05be991>`_)
- Aladin Lite integration. (`f03fbb2 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f03fbb2>`_)
- DataTables integration in results table. (`1324e13 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1324e13>`_)
- Convert database/table location settings to UI form fields. (`6477659 <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6477659>`_)


References
===========

- **Project commit log (GitLab)** – https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commits/master
- **Commit permalink pattern** – ``https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/<SHA>``
- **Keep a Changelog** – https://keepachangelog.com/en/1.1.0/
- **Semantic Versioning 2.0.0** – https://semver.org/spec/v2.0.0.html
- **Towncrier** – https://towncrier.readthedocs.io/
