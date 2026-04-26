# cdac-downloads

Downloadable assets (PDFs, slides, checklists, supplementary materials, manuscripts) linked from the CDAC / BDSP website.

Hosted via GitHub Pages at https://bdsp-core.github.io/cdac-downloads/

This repository was split out from [bdsp-core.github.io](https://github.com/bdsp-core/bdsp-core.github.io) to keep the main site repo lean. References on the main site point at the GitHub Pages URLs above.

## 📋 Still-missing publications

The page at **[/missing/](https://bdsp-core.github.io/cdac-downloads/missing/)** lists every CDAC publication whose link on bdsp-core.github.io still points to PubMed because no PDF exists in this repo yet. Each entry shows clickable DOI / PMC / PubMed buttons (use your library proxy or a browser extension like Lean Library / EZproxy to authenticate at the publisher) and the exact filename to save the downloaded PDF as.

Open that page when you have a free moment to chip away at the remaining list — every PDF you drop in here gets auto-linked on the main site within a day.

## Adding a new file

1. Save the file with the standard filename: `<year>_<lastname>_<journal>_<PMID>.pdf` (use the suggested filename shown on the [/missing/](https://bdsp-core.github.io/cdac-downloads/missing/) page).
2. Drop it in the root of this repo (no subdirectories — keep flat).
3. `git add . && git commit -m "+pdfs" && git push`.
4. The next nightly sync on bdsp-core.github.io will auto-remap the publication's PubMed link to the new PDF — no edits to the main site needed.

## Refreshing the missing/ report

After adding new PDFs, regenerate the missing list:

```bash
python3 make_missing_report.py
git add missing/ && git commit -m "Refresh missing report" && git push
```

The script reads the live publication YAMLs from bdsp-core.github.io and rewrites both `missing/index.html` (the human-friendly report) and `missing/missing-papers.csv` (machine-readable, compatible with [pmc-pdf-downloader](https://github.com/bdsp-core/horrible-things-automator/tree/main/pmc-pdf-downloader)).
