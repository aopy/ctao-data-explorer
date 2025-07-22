# Changelog

All notable changes to **CTAO Data Explorer** are documented in this file.
This file follows *Keep a Changelog* and uses *Semantic Versioning* git tags.

## [Unreleased]

### Changed

- Enable multi-selection in charts and sky map. ([61b837e]).

### Fixed

- Basket: correct time‑zone shift in the basket tab. ([f1014ea]).
- Auth/Session: fix logout; inform user when session expires. ([c07ab7d]).

### Removed

- Remove old ADQL‑hash feature. ([4e1fde4]).

---

## [v0.6.0] – 2025‑07‑08

### Added

- Cache search results in Redis (1 h) to speed up repeat queries. ([136fe8a]).
- Add Simbad/NED dropdown auto-suggestions with Redis-backed caching. ([7c8fe93]).
- Bidirectional selection sync between results table, sky map & charts. ([063d61b]).
- Column descriptions in config; show as tooltips. ([ca149af]).
- Basket UX: add items to multiple baskets; duplicate baskets; provide a default basket. ([5cfc83f]).
- Temporarily store user info (name/email) in Redis; display in profile tab, stop storing user name & email in DB. ([877d952]).
- **Documentation:** initial CHANGELOG draft. ([27e7f6f]).

### Changed

- Object lookup: resolve objects in NED catalogue via `ObjectLookup`; improves object suggestions. ([f9848fc]).
- UI: improve chart & sky map design; adopt Okabe‑Ito colour‑blind–safe palette. ([e103af8]).
- Use standard names for columns in config. ([0bd8b89]).
- Temporarily disable `https_only` in middleware (deployment workaround). ([b46fdfa]).

### Fixed

- Refresh‑token handling. ([f3df089]).
- Object suggestion edge cases. ([b010739]).
- Production callback URL. ([7e6ccdd]).
- Time search issue. ([dec5eca]).

---

## [v0.5.0] – 2025‑06‑06

### Added

- Introduce FastAPI BFF service for auth: store encrypted refresh tokens in the DB and session IDs in Redis. ([c1db462]).

### Changed

- Switch to `date-fns-tz` for timezone formatting. ([51cc2a7]).

### Fixed

- Timeline chart time formatting (locale). ([095c695]).
- Electromagnetic‑range chart min/max energy swap. ([336a054]).
- Query Store summary coordinate/date bug. ([87f5eb1]).

---

## [v0.4.0] – 2025‑04‑25

### Added

- Query Store: persist user queries & results in DB; history tab; store ADQL query hash for (future) caching. ([2fa35db]).

### Changed

- Search form redesigned; add MJD & equatorial HMS/DMS inputs. ([29b7f05]).
- Improve basket‑group structure; allow items in multiple baskets. ([9898f15]).
- Use Astropy Table instead of TAPResults for TAP queries. ([01a6827]).
- Simplify Aladin Lite component; single catalogue. ([9455c4a]).
- Expose API endpoint to fetch basket groups by ID. ([f046f4d]).
- Cookie‑based authentication. ([6ddcb87]).

### Removed

- Drop FastAPI Users extension (only CTAO IAM login used). ([978e728]).

### Fixed

- Build DataLink URL from incoming request. ([c9df34a]).

---

## [v0.3.0] – 2025‑03‑13

### Added

- Record user search history and show it in the user‑profile modal. ([434ebd0]).
- Observation time‑interval search. ([ea13edc]).
- DataLink support. ([605b2eb]).
- Basket functionality. ([01e6001]).
- Modal view of items in the basket tab. ([8a71379]).
- User first name in header. ([3a753c0]).


### Changed

- Multiple basket groups. ([40c310a]).

### Fixed

- Disappearing basket groups. ([d1b5fb7]).

---

## [v0.2.0] – 2025‑01‑27

### Added

- OpenID Connect authentication (FastAPI Users + Authlib). ([1f6727a]).
- Support galactic coordinate system input. ([721fc3e]).
- Object resolve via NED. ([0a23005]).
- Object resolve via Simbad. ([6c349dc]).
- Bootstrap UI. ([d157455]).
- Download button in results table. ([4346006]).

### Changed

- Use TeV in EM chart. ([a7fc6b0]).
- Aladin Lite v3. ([0aff94d]).

### Fixed

- Zooming issue in timeline chart. ([52c705f]).

---

## [v0.1.0] – 2024‑12‑06

### Added

- Electromagnetic‑range chart using Plotly. ([3529438]).
- Timeline chart using Plotly. ([a2f227c]).
- React front‑end. ([e053314]).
- FastAPI back‑end foundation. ([05be991]).
- Aladin Lite integration. ([f03fbb2]).
- DataTables integration in results table. ([1324e13]).
- Convert database/table location settings to UI form fields. ([6477659]).


---

## References

- **Project commit log (GitLab)** – <https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commits/master>
- **Commit permalink pattern** – `https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/<SHA>`
- **Compare pattern** – `https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/<FROM>...<TO>`
- **Keep a Changelog** – <https://keepachangelog.com/en/1.1.0/>
- **Semantic Versioning 2.0.0** – <https://semver.org/spec/v2.0.0.html>

[Unreleased]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.6.0...master
[v0.6.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.5.0...v0.6.0
[v0.5.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.4.0...v0.5.0
[v0.4.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.3.0...v0.4.0
[v0.3.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.2.0...v0.3.0
[v0.2.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.1.0...v0.2.0
[v0.1.0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/tags/v0.1.0

[01a6827]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01a6827
[01e6001]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01e6001
[05a6924]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/05a6924
[05be991]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/05be991
[063d61b]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/063d61b
[095c695]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/095c695
[0bcba33]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0bcba33
[0bd8b89]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0bd8b89
[0dff733]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0dff733
[1017358]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1017358
[11b82ae]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/11b82ae
[1324e13]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1324e13
[136fe8a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/136fe8a
[1f4f89e]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1f4f89e
[24aeafb]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/24aeafb
[27e7f6f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/27e7f6f
[29b7f05]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/29b7f05
[2e1cf3d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/2e1cf3d
[3688bda]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3688bda
[44d4f19]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/44d4f19
[4e1fde4]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/4e1fde4
[51cc2a7]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/51cc2a7
[574635f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/574635f
[5bf10a3]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/5bf10a3
[5cfc83f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/5cfc83f
[605b2eb]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/605b2eb
[63ef9e4]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/63ef9e4
[6477659]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6477659
[68a40c7]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/68a40c7
[6cf3ae0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6cf3ae0
[6e5d8a2]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6e5d8a2
[703ff9f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/703ff9f
[752a2bb]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/752a2bb
[7c8fe93]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7c8fe93
[7e6ccdd]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/7e6ccdd
[818b539]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/818b539
[877d952]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/877d952
[8a71379]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8a71379
[8f0e234]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8f0e234
[9a5df05]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9a5df05
[9f8cbb8]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9f8cbb8
[a28f737]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a28f737
[a7e01ed]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a7e01ed
[ab8f8ef]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ab8f8ef
[b010739]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b010739
[b46fdfa]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b46fdfa
[b6f3cc1]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b6f3cc1
[b90124c]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b90124c
[bc15f71]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/bc15f71
[bf80425]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/bf80425
[c07ab7d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c07ab7d
[c0abcc0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c0abcc0
[c1db462]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c1db462
[ca149af]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ca149af
[c9df34a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/c9df34a
[dec5eca]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/dec5eca
[d157455]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d157455
[e053314]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e053314
[e103af8]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e103af8
[e9a5f24]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/e9a5f24
[f03fbb2]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f03fbb2
[f1014ea]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f1014ea
[f158a2b]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f158a2b
[f18da72]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f18da72
[f3df089]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f3df089
[f9848fc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f9848fc
[feda401]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/feda401
[61b837e]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/61b837e
[336a054]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/336a054
[87f5eb1]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/87f5eb1
[2fa35db]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/2fa35db
[9898f15]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9898f15
[9455c4a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9455c4a
[f046f4d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f046f4d
[6ddcb87]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6ddcb87
[978e728]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/978e728
[434ebd0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/434ebd0
[ea13edc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ea13edc
[3a753c0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3a753c0
[40c310a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/40c310a
[d1b5fb7]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/d1b5fb7
[1f6727a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1f6727a
[721fc3e]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/721fc3e
[0a23005]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0a23005
[6c349dc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6c349dc
[4346006]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/4346006
[a7fc6b0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a7fc6b0
[0aff94d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0aff94d
[52c705f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/52c705f
[3529438]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3529438
[a2f227c]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a2f227c
