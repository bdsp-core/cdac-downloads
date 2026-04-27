#!/usr/bin/env python3
"""
Generate missing/index.html — the list of CDAC publications whose
links on bdsp-core.github.io still point to PubMed because no PDF
exists in this repo.

Run from the cdac-downloads repo root:

    python3 make_missing_report.py

What it does:
  1. Fetches the current publication YAMLs from bdsp-core.github.io
     (gh-pages branch) over HTTPS.
  2. Walks the local *.pdf files; extracts PMIDs from filenames whose
     names end with _<PMID>.pdf.
  3. For each YAML entry whose link.url is a PubMed URL, marks it as
     "still missing" if there's no matching PDF locally.
  4. Writes missing/index.html (clickable DOI / PubMed / preprint links)
     and missing/missing-papers.csv (so you can re-feed the
     pmc-pdf-downloader if NCBI's PoW gate eases up).

To add PDFs to this repo:
  • Click each DOI link (your institutional proxy / browser extension
    routes you to the publisher's PDF).
  • Save as the suggested filename shown in the report (the year /
    first author / journal / PMID convention).
  • Drop into this directory, then `git add . && git commit -m '+pdfs'
    && git push`.
  • The next nightly sync on bdsp-core.github.io will auto-remap the
    PubMed link to the new PDF.
"""

import csv
import html
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml  # PyYAML

REPO_RAW_BASE = "https://raw.githubusercontent.com/bdsp-core/bdsp-core.github.io"
REPO_REF = "gh-pages"  # resolved to a SHA at runtime to bypass CDN cache
YAML_FILES = [
    "_data/publist.yml",
    "_data/yamlHRV_ECG.yml",
    "_data/yamlICUEEGterminology.yml",
    "_data/yamlML_AI.yml",
    "_data/yamlPTE.yml",
    "_data/yamlQEEG.yml",
    "_data/yamlSAH.yml",
    "_data/yamlbrainAge.yml",
    "_data/yamlbreathing.yml",
    "_data/yamlburstSuppression.yml",
    "_data/yamlcEEG.yml",
    "_data/yamlcarT.yml",
    "_data/yamlcardiacArrest.yml",
    "_data/yamlclosedLoopControl.yml",
    "_data/yamlcompNeuro.yml",
    "_data/yamlconnectivity.yml",
    "_data/yamlcovid.yml",
    "_data/yamldecisionAnalysis.yml",
    "_data/yamldelirium.yml",
    "_data/yamldementia.yml",
    "_data/yamleeg.yml",
    "_data/yamlehrPhenotyping.yml",
    "_data/yamlepilepsySurgery.yml",
    "_data/yamlgenNeuro.yml",
    "_data/yamlinfoTheory.yml",
    "_data/yamlinsomnia.yml",
    "_data/yamlnoiseAndBias.yml",
    "_data/yamlnon_neuro_informatics.yml",
    "_data/yamlprobStatsCausal.yml",
    "_data/yamlriskPrediction.yml",
    "_data/yamlsedationAndAnesthesia.yml",
    "_data/yamlseizures.yml",
    "_data/yamlsleepStaging.yml",
    "_data/yamlspikeDetection.yml",
    "_data/yamlspindles.yml",
    "_data/yamlstatusEpilepticus.yml",
    "_data/yamlszForecasting.yml",
    "_data/yamlszIIIC.yml",
    "_data/yamlszIIIC_harm.yml",
    "_data/yamlszRisk.yml",
    "_data/yamltimeSeries.yml",
    "_data/yamltpw.yml",
]

PMID_URL_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{7,9})")
PMID_DISP_RE = re.compile(r"PMID[:\s]*(\d{7,9})")
PMCID_RE = re.compile(r"PMCID[:\s]*(PMC\d+)")
DOI_RE = re.compile(r"doi[:\s]*(10\.\d{3,9}/[^\s.;,]+(?:\.[^\s.;,]+)*)", re.I)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
JOURNAL_RE = re.compile(r"^\s*([^.\n]+?)\s+(?:19|20)\d{2}")
PDF_PMID_RE = re.compile(r"_(\d{7,9})\.pdf$", re.I)


def slug(s, n=30):
    s = (s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", s)[:n] or "Unknown"


def suggested_filename(p):
    first = (p["authors"] or "").split(",")[0].strip().split()
    return (
        f"{p['year'] or 'XXXX'}_"
        f"{slug(first[0] if first else '')}_"
        f"{slug(p['journal'])}_"
        f"{p['pmid']}.pdf"
    )


_resolved_sha = None


def _ref_sha():
    """Resolve REPO_REF to its current commit SHA via the GitHub API.
    Pinning fetches to a SHA bypasses raw.githubusercontent.com's branch-
    level CDN cache (which can be minutes stale on hot branches)."""
    global _resolved_sha
    if _resolved_sha:
        return _resolved_sha
    api = f"https://api.github.com/repos/bdsp-core/bdsp-core.github.io/branches/{REPO_REF}"
    try:
        with urllib.request.urlopen(api, timeout=30) as r:
            import json
            _resolved_sha = json.loads(r.read())["commit"]["sha"]
    except Exception:
        _resolved_sha = REPO_REF  # fall back to branch name
    return _resolved_sha


def fetch_yaml(rel_path):
    url = f"{REPO_RAW_BASE}/{_ref_sha()}/{rel_path}"
    req = urllib.request.Request(url, headers={"User-Agent": "cdac-downloads/missing-report"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return yaml.safe_load(r.read().decode("utf-8")) or []


def collect_missing():
    here = Path(__file__).resolve().parent
    have_pmids = set()
    for f in here.iterdir():
        m = PDF_PMID_RE.search(f.name)
        if m:
            have_pmids.add(m.group(1))

    missing = {}  # pmid -> dict
    for path in YAML_FILES:
        try:
            data = fetch_yaml(path)
        except Exception as e:
            print(f"  WARN: couldn't fetch {path}: {e}")
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            link = entry.get("link") or {}
            url = link.get("url", "") or ""
            display = link.get("display", "") or ""
            m = PMID_URL_RE.search(url)
            if not m:
                continue
            pmid = m.group(1)
            if pmid in have_pmids or pmid in missing:
                continue
            doi_m = DOI_RE.search(display)
            year_m = YEAR_RE.search(display)
            pmcid_m = PMCID_RE.search(display)
            journ_m = JOURNAL_RE.search(display)
            missing[pmid] = {
                "pmid": pmid,
                "title": (entry.get("title") or "").strip().strip('"').strip("'"),
                "authors": (entry.get("authors") or "").strip(),
                "year": year_m.group(0) if year_m else "",
                "journal": journ_m.group(1).strip() if journ_m else "",
                "doi": doi_m.group(1) if doi_m else "",
                "pmcid": pmcid_m.group(1) if pmcid_m else "",
                "display": display.strip(),
            }
    return missing


def write_csv(missing, out_path):
    cols = ["PMID", "Title", "Authors", "Year", "Journal", "PMCID", "DOI", "Suggested Filename"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for p in sorted(missing.values(), key=lambda x: (x["year"] or "0"), reverse=True):
            w.writerow([p["pmid"], p["title"], p["authors"], p["year"], p["journal"],
                        p["pmcid"], p["doi"], suggested_filename(p)])


def write_html(missing, out_path):
    by_year = defaultdict(list)
    for p in missing.values():
        by_year[p["year"] or "????"].append(p)
    years = sorted(by_year.keys(), reverse=True)
    n = len(missing)
    n_pmcid = sum(1 for p in missing.values() if p["pmcid"])
    n_doi = sum(1 for p in missing.values() if p["doi"])

    parts = []
    parts.append(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CDAC publications — still missing PDFs</title>
<style>
  body {{ font: 15px/1.4 system-ui, -apple-system, sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; color: #222; }}
  h1 {{ margin-bottom: 0.2em; }}
  .summary {{ color: #666; margin-bottom: 2em; }}
  h2 {{ margin-top: 2em; padding-top: 0.4em; border-top: 1px solid #ddd; }}
  .paper {{ margin-bottom: 1.2em; padding-bottom: 0.6em; border-bottom: 1px dotted #eee; }}
  .title {{ font-weight: 600; }}
  .meta {{ color: #555; font-size: 0.93em; margin: 0.15em 0; }}
  .links a {{ display: inline-block; margin-right: 0.7em; padding: 1px 6px; border-radius: 3px; background: #eef; color: #034; text-decoration: none; font-size: 0.9em; }}
  .links a:hover {{ background: #cce; }}
  .filename {{ color: #888; font-family: ui-monospace, monospace; font-size: 0.85em; margin-top: 0.2em; }}
  .nopmcid {{ color: #c40; }}
  .haspmcid {{ color: #480; }}
  details {{ margin-top: 0.3em; }}
  summary {{ cursor: pointer; color: #888; font-size: 0.85em; }}
  .display {{ color: #777; font-size: 0.85em; padding-left: 1em; }}
</style>
</head>
<body>
<h1>CDAC publications — still missing PDFs</h1>
<p class="summary">
  {n} unique publications still link to PubMed because no PDF exists in
  <a href="https://github.com/bdsp-core/cdac-downloads">cdac-downloads</a>.
  {n_pmcid} have a PMCID (PoW-gated; auto-fetcher couldn't pull them).
  {n_doi} have a DOI (try clicking — your library proxy / browser extension
  may route to the publisher's PDF). Save downloads with the
  <code>suggested-filename.pdf</code> shown beneath each paper, drop into
  the cdac-downloads repo, and the next nightly remap on
  bdsp-core.github.io will switch the link automatically.
</p>
""")

    for year in years:
        items = by_year[year]
        parts.append(f'<h2>{html.escape(str(year))} <span style="color:#aaa;font-weight:normal;font-size:0.7em">({len(items)})</span></h2>')
        for p in items:
            doi_link = (
                f'<a href="https://doi.org/{html.escape(p["doi"])}">DOI</a>'
                if p["doi"] else ""
            )
            pmid_link = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{p["pmid"]}/">PubMed</a>'
            pmc_link = (
                f'<a href="https://pmc.ncbi.nlm.nih.gov/articles/{html.escape(p["pmcid"])}/">PMC</a>'
                if p["pmcid"] else ""
            )
            pmcid_class = "haspmcid" if p["pmcid"] else "nopmcid"
            pmcid_label = p["pmcid"] if p["pmcid"] else "no PMC entry"
            parts.append(f"""<div class="paper">
  <div class="title">{html.escape(p['title'])}</div>
  <div class="meta">{html.escape(p['authors'])}</div>
  <div class="meta"><i>{html.escape(p['journal'])}</i> · PMID {p['pmid']} · <span class="{pmcid_class}">{pmcid_label}</span></div>
  <div class="links">{doi_link}{pmc_link}{pmid_link}</div>
  <div class="filename">→ save as: {html.escape(suggested_filename(p))}</div>
  <details><summary>display string</summary><div class="display">{html.escape(p['display'])}</div></details>
</div>
""")

    parts.append("</body></html>")
    out_path.write_text("".join(parts), encoding="utf-8")


def main():
    here = Path(__file__).resolve().parent
    out_dir = here / "missing"
    out_dir.mkdir(exist_ok=True)
    print("Fetching YAMLs from bdsp-core.github.io (gh-pages)...")
    missing = collect_missing()
    print(f"Found {len(missing)} publications still missing PDFs.")

    write_html(missing, out_dir / "index.html")
    write_csv(missing, out_dir / "missing-papers.csv")
    print(f"Wrote: {out_dir / 'index.html'}")
    print(f"Wrote: {out_dir / 'missing-papers.csv'}")
    print()
    print(f"Open https://bdsp-core.github.io/cdac-downloads/missing/ after pushing,")
    print(f"or open the file directly: file://{out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
