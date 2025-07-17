# Changelog

All notable changes to **CTAO Data Explorer** will be documented in this file.

The structure follows the recommendations of *Keep a Changelog* and is intended to be compatible with *Semantic Versioning* once formal release tags are introduced. Until tags exist, entries are grouped by the date of the latest commit in each batch (reverse chronological).

For the complete, fine‑grained commit history, see the project repository’s commit list on GitLab.

## [Unreleased]

## [2025-07-16 – Latest]

### Added

- Cache search results in Redis (1 hour) to speed up repeat queries. ([136fe8a]).
- Add initial CHANGELOG. ([27e7f6f]).

### Changed

- Object lookup: resolve objects in NED catalogue via ObjectLookup; improves object suggestions. ([f9848fc]).

### Fixed

- Basket: correct time shift / timezone display in basket tab. ([f1014ea]).
- Auth/Session: fix logout; inform user when session expires. ([c07ab7d]).

### Removed

- Remove old ADQL-hash feature. ([4e1fde4]).

## [2025-06-30]

### Added

- Auto-suggest objects via dropdown as you type the source name; temporary cache suggestions via Redis. ([7c8fe93]).
- Bidirectional selection sync between results table, sky map & charts. ([063d61b]).
- Column descriptions in config; show as tooltips. ([ca149af]).
- Basket UX: add items to multiple baskets; duplicate baskets; provide a default basket. ([5cfc83f]).
- Temporarily store user info (name/email) in Redis; display in profile tab, stop storing user name, email in DB. ([877d952]).
- New auth/BFF service architecture managing external tokens; store encrypted refresh token in DB, session ID in Redis. ([c1db462]).

### Changed

- UI: improve chart & sky map design; adopt Okabe & Ito colour-blind safe palette. ([e103af8]).
- Use standard names for columns in config. ([0bd8b89]).
- Switch to date-fns-tz for timezone formatting. ([51cc2a7]).
- Temporarily disable https_only in middleware (deployment workaround). ([b46fdfa]).

### Fixed

- Refresh token handling. ([f3df089]).
- Object suggestion edge cases. ([b010739]).
- Production callback URL. ([7e6ccdd]).
- Time search issue. ([dec5eca]).

## [2025-05-28]

### Added

- Results table: per‑column sort controls. ([8687016]).
- Results table: hide/show all columns toggles. ([a9bf0fe]).
- Search form field tooltips. ([8e92793]).
- Search form: clear button. ([f18da72]).
- Persist search form values in sessionStorage prior to login. ([ae0f83c]).
- Safeguards & warnings for MJD→date conversions. ([71494da]).
- Query Store summary: show equatorial HMS/DMS. ([683462a]).

### Changed

- Build DataLink URL from incoming request. ([c9df34a]).

### Fixed

- Timeline chart time formatting (locale). ([095c695]).
- EM chart min/max energy swap. ([336a054]).
- Query Store summary coordinate/date bug. ([87f5eb1]).

## [2025-04-25]

### Added

- Query Store: persist user queries & results in DB; history tab; reload past queries; store ADQL query hash for (future) caching. ([2fa35db]).
- Allow items to belong to multiple baskets. ([9898f15]).
- Cookie‑based authentication. ([6ddcb87]).

### Changed

- Search form redesigned; add MJD & equatorial HMS/DMS inputs. ([29b7f05]).
- Use Astropy Table instead of TAPResults for TAP queries. ([01a6827]).
- Simplify Aladin Lite component; single catalogue. ([9455c4a]).
- Expose API endpoint to fetch basket groups by ID. ([f046f4d]).

### Removed

- Drop FastAPI Users extension (only CTAO IAM login used). ([978e728]).

### Fixed

- Temporary workaround for VOTable floating‑point issue. ([5921ddc]).

## [2025-03-17]

### Added

- Multiple basket groups per user. ([40c310a]).

### Changed

- Extend user schema/profile (email, first login). ([60cde7b]).
- Record user search history (params/results) in DB; show JSON in profile modal. ([434ebd0]).

## [2025-02-28]

### Added

- Observation time‑interval (UTC) search filter. ([ea13edc]).
- Search by observation date. ([1017358]).
- DataLink support (initial; local testing). ([c0abcc0]).
- Basket item detail modal (sky map & charts) from basket. ([8a71379]).
- Add selected results to basket. ([01e6001]).
- Results table: hide/show columns toggles. ([feda401]).

### Changed

- Present DataLink services as dropdown in result rows. ([605b2eb]).
- Prevent duplicate adds to basket; improve item display & warnings. ([e9a5f24]).
- Improve auto zoom‑out in sky map for large regions. ([bf80425]).

### Fixed

- DataLink dropdown issues; support `service_def` in VOTable. ([8b162a2]).

### Removed

- Remove duplicate `access_url` column; improve long column‑name display. ([b245762]).

## [2025-01-29]

### Added

- Authentication via CTAO IAM / OpenID Connect (FastAPI Users + Authlib, Postgres backend); includes Alembic migrations; unified JWT secret; async DB user storage. ([1f6727a]).
- Support galactic coordinates in search form. ([721fc3e]).

### Changed

- Display user's name in header; record first‑login timestamp for analytics. ([502754d]).
- Integrate second NED TAP catalogue in object resolver. ([0a23005]).

## [2024-12-20]

### Added

- Object resolution via Simbad TAP in search form. ([6c349dc]).
- EM range chart (Plotly). ([3529438]).
- Timeline chart (Plotly). ([a2f227c]).
- Download button in `access_url` column. ([67b459f]).

### Changed

- Add TeV energy values; adjust EM chart transparency & colours. ([a7fc6b0]).
- Indicate units in search form labels; set default search radius. ([67b459f]).
- Upgrade to Aladin Lite v3. ([0aff94d]).
- Adopt Bootstrap for UI. ([d157455]).

### Fixed

- Timeline chart zoom behaviour. ([52c705f]).

## [2024-11-29]

### Added

- DataTables integration in results table (sorting/filtering). ([1324e13]).

### Changed

- Keep all sky map markers visible across zoom levels. ([0bcba33]).
- Integrate Aladin Lite into search results. ([f03fbb2]).
- Convert DB/table path settings to UI form fields. ([6477659]).
- Split frontend into dedicated React client. ([e053314]).
- Initial release with core search features. ([05be991]).

---

## References

**Project history**
- Project commit log (GitLab): see the full list of commits.  <!-- canonical -->
- Commit permalink pattern: `https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/<SHA>`
- Compare/diff pattern: `https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/<FROM>...<TO>`
  - `<FROM>` / `<TO>` can be tags, branch names, or commit SHAs.

**Changelog & versioning style guides**
- Keep a Changelog — https://keepachangelog.com/en/1.1.0/
- Semantic Versioning 2.0.0 — https://semver.org/spec/v2.0.0.html
- Conventional Commits (optional prefix style) — https://www.conventionalcommits.org/en/v1.0.0/

---

### Link reference definitions (to be updated after tagging)

<!--
Example tag cut points:
- v0.3.0  (2025-07-16)  fix TZ shift; Redis caching; NED lookup; cleanup
- v0.2.0  (2025-06-16)  basket enhancements; table/tooltips; UI polish; auth fixes
- v0.1.0  (2024-11-21)  initial public release
After creating tags, update the links below.
-->

[Unreleased]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.3.0...master
[v0.3.0]:    https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.2.0...v0.3.0
[v0.2.0]:    https://gitlab.obspm.fr/oates/ctao-data-explorer/-/compare/v0.1.0...v0.2.0
[v0.1.0]:    https://gitlab.obspm.fr/oates/ctao-data-explorer/-/tree/05be991

[01a6827]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01a6827
[01e6001]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/01e6001
[05a6924]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/05a6924
[05be991]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/05be991
[063d61b]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/063d61b
[095c695]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/095c695
[09cjtbd-placeholder]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/09cjtbd-placeholder
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
[95cjdps-placeholder]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/95cjdps-placeholder
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
[8687016]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8687016
[52c705f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/52c705f
[0aff94d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0aff94d
[67b459f]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/67b459f
[a7fc6b0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a7fc6b0
[a2f227c]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a2f227c
[3529438]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/3529438
[0a23005]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/0a23005
[502754d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/502754d
[721fc3e]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/721fc3e
[1f6727a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/1f6727a
[b245762]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/b245762
[8b162a2]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8b162a2
[ea13edc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ea13edc
[434ebd0]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/434ebd0
[60cde7b]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/60cde7b
[40c310a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/40c310a
[5921ddc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/5921ddc
[978e728]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/978e728
[6ddcb87]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6ddcb87
[9898f15]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9898f15
[2fa35db]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/2fa35db
[87f5eb1]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/87f5eb1
[336a054]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/336a054
[f046f4d]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/f046f4d
[9455c4a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/9455c4a
[a9bf0fe]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/a9bf0fe
[8e92793]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/8e92793
[ae0f83c]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/ae0f83c
[71494da]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/71494da
[683462a]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/683462a
[6c349dc]: https://gitlab.obspm.fr/oates/ctao-data-explorer/-/commit/6c349dc
