"""Refresh the studies listed on the homepage, keeping the curated media links."""
import argparse
import html
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SCHOLAR = "https://scholar.google.com/citations?user=EHnCIIwAAAAJ&hl=en"
SCHOLAR_RECENT = SCHOLAR + "&view_op=list_works&sortby=pubdate"
ARXIV = "https://export.arxiv.org/api/query?" + urlencode({
    "search_query": "au:Sergeyuk", "start": 0, "max_results": 100,
    "sortBy": "submittedDate", "sortOrder": "descending",
})
OPENALEX = "https://api.openalex.org/works?" + urlencode({
    "filter": "author.id:A5048973290", "per_page": 100,
    "select": "display_name,doi,publication_year,primary_location,type",
})
KAIROS = "https://kairos.jetbrains.com/sitemap.xml"
JETBRAINS = "https://blog.jetbrains.com/author/agnia-sergeyuk/"
START = "<!-- publications:start -->"
END = "<!-- publications:end -->"


def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def title_key(title):
    key = "".join(char for char in unicodedata.normalize("NFKC", title).casefold() if char.isalnum())
    if key == "understandingpromptprogrammingtasksandquestions":
        return "understandingdeveloperinformationneedsforsoftwarewithembeddednaturallanguageprompts"
    return key


def fetch(url):
    request = Request(url, headers={"User-Agent": "HugniaPortfolio/1.0 (+https://github.com/hugnia)"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def parse_scholar(page):
    studies = []
    for row in re.findall(r'<tr\b[^>]*class="gsc_a_tr"[^>]*>(.*?)</tr>', page, re.S):
        title = re.search(r'<a\b[^>]*class="gsc_a_at"[^>]*>(.*?)</a>', row, re.S)
        year = re.search(r'<span class="gsc_a_h gsc_a_hc gs_ibl">(\d{4})</span>', row)
        if not title or not year:
            continue
        href = re.search(r'href="([^"]+)"', title[0])
        if href:
            url = urljoin(SCHOLAR, html.unescape(href[1]))
            if urlsplit(url).hostname == "scholar.google.com":
                studies.append({"title": clean(title[1]), "year": int(year[1]), "scholar": url})
    return studies


def parse_arxiv(feed):
    studies = []
    for entry in ElementTree.fromstring(feed).findall("{*}entry"):
        authors = {title_key(author.findtext("{*}name", "")) for author in entry.findall("{*}author")}
        if "agniasergeyuk" not in authors:
            continue
        identifier = re.search(r"/abs/(\d{4}\.\d+)", entry.findtext("{*}id", ""))
        if identifier:
            studies.append({
                "title": clean(entry.findtext("{*}title", "")),
                "year": int(entry.findtext("{*}published")[:4]),
                "arxiv": f"https://arxiv.org/abs/{identifier[1]}",
            })
    return studies


def parse_openalex(payload):
    studies = []
    for work in json.loads(payload)["results"]:
        doi = work["doi"]
        if work["type"] in {"dataset", "erratum", "paratext"} or not doi:
            continue
        record = {"title": clean(work["display_name"]), "year": work["publication_year"]}
        preprint = re.fullmatch(r"https://doi\.org/10\.48550/arxiv\.(\d{4}\.\d+)", doi, re.I)
        if preprint:
            record["arxiv"] = f"https://arxiv.org/abs/{preprint[1]}"
        elif doi.startswith("https://doi.org/10."):
            record["paper"] = doi
            location = work.get("primary_location") or {}
            venue = (location.get("source") or {}).get("display_name")
            if venue:
                record["venue"] = venue
        else:
            continue
        studies.append(record)
    return studies


def merge_studies(*sources):
    studies = []
    for source in sources:
        for incoming in source:
            identifiers = {(key, incoming[key].casefold()) for key in ("paper", "arxiv") if key in incoming}
            match = next(
                (study for study in studies if title_key(study["title"]) == title_key(incoming["title"])
                 or any(study.get(key, "").casefold() == value for key, value in identifiers)),
                None,
            )
            if match is None:
                studies.append(dict(incoming))
                continue
            if "paper" in incoming and "paper" not in match:
                match.update({key: incoming[key] for key in ("title", "year")})
            for key, value in incoming.items():
                if key in {"writeups", "videos"}:
                    links = match.get(key, [])
                    known_urls = {item["url"].rstrip("/") for item in links}
                    match[key] = links + [item for item in value if item["url"].rstrip("/") not in known_urls]
                else:
                    match.setdefault(key, value)
    return sorted(studies, key=lambda study: (-study["year"], title_key(study["title"])))


def read_article(url):
    try:
        page = fetch(url)
    except (OSError, ValueError) as error:
        print(f"Could not read {url}: {error}", file=sys.stderr)
        return url, "", set()
    match = re.search(r"<title\b[^>]*>(.*?)</title>", page, re.I | re.S)
    title = clean(match[1]) if match else ""
    title = re.split(r"\s+(?:—|–|-)\s+(?:JetBrains Research|The JetBrains Blog)", title)[0]
    dois = re.findall(r"(?:doi\.org/|dl\.acm\.org/doi/(?:abs/|full/)?)(10\.\d+/[\w./()-]+)", page, re.I)
    preprints = re.findall(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d+)", page, re.I)
    references = {f"https://doi.org/{doi.casefold().rstrip(').')}" for doi in dois}
    references.update(f"https://arxiv.org/abs/{identifier}" for identifier in preprints)
    return url, title, references


def add_matching_writeups(studies, sitemap, archive):
    urls = {
        node.text for node in ElementTree.fromstring(sitemap).findall(".//{*}loc")
        if node.text and node.text.startswith("https://kairos.jetbrains.com/research/articles/")
    }
    urls.update(re.findall(r'href="(https://blog\.jetbrains\.com/research/20\d{2}/\d{2}/[a-z0-9-]+/)"', archive))
    existing = {link["url"].rstrip("/") for study in studies for link in study.get("writeups", [])}
    urls = {url for url in urls if url.rstrip("/") not in existing}
    by_title = {title_key(study["title"]): study for study in studies}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for url, title, references in pool.map(read_article, sorted(urls)):
            study = by_title.get(title_key(title))
            if not study:
                matches = [item for item in studies if any(
                    item.get(key, "").casefold() in references for key in ("paper", "arxiv")
                )]
                study = matches[0] if len(matches) == 1 else None
            if study:
                label = "Kairos write-up" if urlsplit(url).hostname == "kairos.jetbrains.com" else "JetBrains write-up"
                study.setdefault("writeups", []).append({"label": label, "url": url})


def link(label, url):
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError(f"Expected an HTTPS publication link: {url}")
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)} <span aria-hidden="true">↗</span></a>'


def render(studies):
    rows = []
    for study in studies:
        venue = study.get("venue") or ("Preprint" if study.get("arxiv") else "")
        metadata = f'{study["year"]} · {venue}' if venue else str(study["year"])
        links = []
        if study.get("paper"):
            links.append(link(study.get("paper_label", "Paper"), study["paper"]))
        if study.get("arxiv"):
            links.append(link("arXiv", study["arxiv"]))
        if not links and study.get("scholar"):
            links.append(link("Google Scholar", study["scholar"]))
        links.extend(link(item["label"], item["url"]) for item in study.get("writeups", []))
        links.extend(link(item["label"], item["url"]) for item in study.get("videos", []))
        rows.append(
            "          <li class=\"study\">\n"
            f'            <p class="label">{html.escape(metadata)}</p>\n'
            f'            <h3>{html.escape(study["title"])}</h3>\n'
            f'            <div class="study-links">{"".join(links)}</div>\n'
            "          </li>"
        )
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Render the checked-in catalogue only.")
    parser.add_argument("--snapshot", type=Path, help="Keep studies discovered on previous runs.")
    args = parser.parse_args()
    baseline = json.loads((ROOT / "data" / "publications.json").read_text())
    sources = [baseline]
    if args.snapshot and args.snapshot.is_file():
        sources.append(json.loads(args.snapshot.read_text()))
    if not args.offline:
        for name, url, parse in (
            ("arXiv", ARXIV, parse_arxiv), ("OpenAlex", OPENALEX, parse_openalex),
            ("Google Scholar", SCHOLAR_RECENT, parse_scholar),
        ):
            try:
                records = parse(fetch(url))
                if not records:
                    raise ValueError("no usable publications returned")
                sources.append(records)
                print(f"{name}: {len(records)} records")
            except (OSError, ValueError, KeyError, ElementTree.ParseError) as error:
                if name != "Google Scholar":
                    raise RuntimeError(f"{name} refresh failed: {error}") from error
                print(f"Google Scholar refresh skipped: {error}", file=sys.stderr)
    studies = merge_studies(*sources)
    if not args.offline:
        try:
            add_matching_writeups(studies, fetch(KAIROS), fetch(JETBRAINS))
        except (OSError, ValueError, ElementTree.ParseError) as error:
            print(f"Write-up discovery skipped: {error}", file=sys.stderr)

    index = ROOT / "index.html"
    page = index.read_text()
    before, start, rest = page.partition(START)
    _, end, after = rest.partition(END)
    if not start or not end:
        raise ValueError("Could not locate the publication list in index.html")
    index.write_text(f"{before}{START}\n{render(studies)}\n          {END}{after}")
    if args.snapshot and not args.offline:
        args.snapshot.write_text(json.dumps(studies, ensure_ascii=False, indent=2) + "\n")
    print(f"Rendered {len(studies)} publications")


if __name__ == "__main__":
    main()
