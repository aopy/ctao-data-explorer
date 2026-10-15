# Architecture and download diagrams

The architecture page includes `general-architecture.svg`. The download-flows page
includes `single-file-browser-download.svg` and `bulk-download.svg`. Matching `.mmd`
files are editable Mermaid sources and are offered as downloads from those pages.

The checked-in SVGs preserve the reviewed custom layout. Mermaid describes the same
components and flows, with some sequence steps expanded explicitly. A Mermaid CLI
export will produce a different automatic layout; check readability before replacing
an SVG. The architecture SVG includes only the overview, not its three detail views.

To regenerate an SVG from Mermaid, run from the repository root with Node.js and
Mermaid CLI available (Mermaid 11 syntax; sources checked with Mermaid 11.17.2):

```sh
npx --package @mermaid-js/mermaid-cli@11.17.0 mmdc -i docs/diagrams/general-architecture.mmd -o docs/diagrams/general-architecture.svg
npx --package @mermaid-js/mermaid-cli@11.17.0 mmdc -i docs/diagrams/single-file-browser-download.mmd -o docs/diagrams/single-file-browser-download.svg
npx --package @mermaid-js/mermaid-cli@11.17.0 mmdc -i docs/diagrams/bulk-download.mmd -o docs/diagrams/bulk-download.svg
```

Mermaid CLI needs a supported browser and may download tooling on first use.
Sphinx's figure directives require no changes to `docs/conf.py` or Python
dependencies. Check the generated documentation at normal reading width and open
the standalone SVG for long sequences.
