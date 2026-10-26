#!/usr/bin/env python3
"""
How COHO cites where a quote was read, and the step that gives every quote read in a paper its paper's identifier.

Every quote in the curation tables records the paper it was read in, in the `PMID` column (PMID:n; DOI:... for a
paper that PubMed does not index, or PMCID:PMCn for one with neither; empty for a record or a website), and the address its text was fetched from, in
the `read at` column, which is kept for verification and is not itself cited. On the annotated axiom
(oboInOwl:hasDbXref) the ontology cites:
  - a paper by its PMID or DOI, never by the address it was read at (a Europe PMC, PMC, PubMed, BioC or E-utilities
    address, a DOI link, a publisher's page, a copy in a repository);
  - a supplementary file by its paper's PMID or DOI and the file's own URL, on the publisher's canonical host;
  - a medRxiv or bioRxiv preprint read in place of the published paper by the preprint's DOI as well;
  - a database record by its public page (a GWAS Catalog study, an EGA study or dataset, a PGS Catalog score or
    publication, a ClinicalTrials.gov or ISRCTN study, a MetaboLights study, a PRIDE project, a dbGaP study, a
    BioProject), never by its API address; a PGS Catalog cohort, which has no page, by its REST record;
  - anything else with a DOI (a report, a dataset) by the DOI, and anything else (a cohort's website, an archived
    page) by the address it was read at.
The source-form QC check holds the release to these forms.

Run as a script, it fills each empty PMID cell of the evidence tables whose quote was read in a paper its address
identifies (by PMC id, PMID, DOI or Elsevier PII), from PMC's ID converter, Europe PMC and Crossref, and replaces a
DOI with the paper's PMID once PubMed has one; cites the papers given by address among the definitions' sources
(definitions_curated.tsv) and the sub-cohort links of the edit file by PMID; and lists what it could not resolve. A
definition's other sources are left as its drafter cited them. With --check it also compares every row's PMID with
the paper of the address it was read at, and exits with an error if any differs: the quote was read in that paper,
so the PMID is corrected to it, or the address if the quote was in fact read elsewhere.

Usage: src/scripts/sources.py [--dry-run] [--check]
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

CUR = M.CUR
# the tables whose rows record a quote with its paper (PMID) and the address it was read at
TABLES = ["definition_quotes.tsv", "name_evidence.tsv", "type_evidence.tsv", "location_curated.tsv", "cohort_participants.tsv",
          "cohort_diseases.tsv", "cohort_exposures.tsv", "aggregation_members_curated.tsv", "review_evidence.tsv"]
PAPER_ID = re.compile(r"^(PMID:\d+|DOI:10\.\S+|PMCID:PMC\d+)$")


@dataclass
class Source:
    kind: str  # paper, supplement, preprint, doi, record or website
    url: str = ""  # what to cite for a supplement (the file), a record (its page) or a website (the address)
    pmid: str = ""
    pmcid: str = ""
    doi: str = ""
    pii: str = ""
    guess: bool = False  # a DOI made from a Nature article id, which only a lookup confirms


def _q(s):
    return urllib.parse.unquote(s)


RECORDS = [  # (address, public page)
    (r"https?://www\.pgscatalog\.org/(?:rest/)?score/(PGS\d+)", "https://www.pgscatalog.org/score/{}/"),
    (r"https?://www\.pgscatalog\.org/(?:rest/)?publication/(PGP\d+)", "https://www.pgscatalog.org/publication/{}/"),
    (r"https?://www\.pgscatalog\.org/rest/cohort/([^?#]+)", "https://www.pgscatalog.org/rest/cohort/{}"),
    (r"https?://www\.ebi\.ac\.uk/gwas/(?:rest/api/(?:v2/)?)?studies/(GCST\d+)", "https://www.ebi.ac.uk/gwas/studies/{}"),
    (r"https?://(?:metadata\.)?ega-archive\.org/studies/(EGAS\d+)", "https://ega-archive.org/studies/{}"),
    (r"https?://(?:metadata\.)?ega-archive\.org/datasets/(EGAD\d+)", "https://ega-archive.org/datasets/{}"),
    (r"https?://(?:classic\.)?clinicaltrials\.gov/(?:api/v2/studies|ct2/show|study|show)/(NCT\d+)", "https://clinicaltrials.gov/study/{}"),
    (r"https?://www\.isrctn\.com/(?:api/query/format/default\?q=)?(ISRCTN\d+)", "https://www.isrctn.com/{}"),
    (r"https?://www\.ebi\.ac\.uk/metabolights/(?:ws/studies/(?:public/study/)?|editor/)?(MTBLS\d+)", "https://www.ebi.ac.uk/metabolights/{}"),
    (r"https?://www\.ebi\.ac\.uk/pride/(?:ws/archive/v\d/projects|archive/projects)/(PXD\d+)", "https://www.ebi.ac.uk/pride/archive/projects/{}"),
    (r"https?://www\.ncbi\.nlm\.nih\.gov/projects/gap/cgi-bin/study\.cgi\?study_id=(phs\d+(?:\.v\d+\.p\d+)?)",
     "https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={}"),
    (r"https?://ftp\.ncbi\.nlm\.nih\.gov/dbgap/studies/phs\d+/(phs\d+\.v\d+\.p\d+)/GapExchange_",
     "https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={}"),
    (r"https?://www\.ncbi\.nlm\.nih\.gov/bioproject/(?:PRJNA)?(\d+)", "https://www.ncbi.nlm.nih.gov/bioproject/{}"),
]
# publishers' and repositories' pages of papers whose address does not name the paper
PUBLISHED = re.compile(
    r"https?://(?:www\.nature\.com/articles/|link\.springer\.com/(?:article|chapter|content/pdf)/|[\w-]+\.biomedcentral\.com/articles/"
    r"|journals\.plos\.org/\w+/article|www\.frontiersin\.org/(?:journals/[^/]+/)?articles/|openbioresources\.metajnl\.com/articles/"
    r"|(?:onlinelibrary\.wiley\.com|www\.tandfonline\.com|www\.ahajournals\.org|journals\.sagepub\.com|www\.nejm\.org|www\.science\.org"
    r"|www\.pnas\.org|ascopubs\.org|www\.atsjournals\.org|journals\.physiology\.org|www\.liebertpub\.com)/doi/"
    r"|www\.sciencedirect\.com/science/article/|www\.(?:cell|thelancet)\.com/|academic\.oup\.com/[^/]+/article"
    r"|www\.cambridge\.org/core/journals/[^/]+/article/|(?:[\w-]+\.)?bmj\.com/content/|jamanetwork\.com/journals/|(?:www\.)?karger\.com/"
    r"|www\.mdpi\.com/|journals\.lww\.com/|diabetesjournals\.org/|www\.jci\.org/articles/|www\.jstage\.jst\.go\.jp/article/"
    r"|elifesciences\.org/articles/|haematologica\.org/article/|jtd\.amegroups\.org/article/|[\w.-]+/journal/view\.php\?doi="
    r"|jkms\.org/DOIx\.php|koreascience\.or\.kr/article/|www\.dovepress\.com/|www\.journalslibrary\.nihr\.ac\.uk/)", re.I)
SUPPLEMENTS = re.compile(
    r"https?://(?:cdn-links\.lww\.com/permalink/|(?:ndownloader\.)?figshare\.com/(?:ndownloader/)?files/|oup\.silverchair-cdn\.com/"
    r"|[\w-]+\.bmj\.com/content/\w+/early/.*/DC\d+/embed/)", re.I)


def classify(url):
    """What the address `url` is, with the identifiers it carries."""
    u = url.strip()

    def m(p):
        return re.match(p, u, re.I)

    # Europe PMC
    if x := m(r"https?://www\.ebi\.ac\.uk/europepmc/webservices/rest/(PMC\d+)/supplementaryFiles"):
        return Source("supplement", u, pmcid=x[1].upper())
    if x := m(r"https?://www\.ebi\.ac\.uk/europepmc/webservices/rest/(PMC\d+)/"):
        return Source("paper", pmcid=x[1].upper())
    if x := m(r"https?://www\.ebi\.ac\.uk/europepmc/webservices/rest/search\?(.*)"):
        q = urllib.parse.parse_qs(x[1]).get("query", [""])[0]
        if (y := re.search(r'EXT_ID:\s*"?(\d+)"?', q, re.I)) and (not re.search(r"SRC:", q, re.I) or re.search(r"SRC:\s*MED", q, re.I)):
            return Source("paper", pmid=y[1])
        if y := re.search(r'PMCID:\s*"?(PMC\d+)', q, re.I):
            return Source("paper", pmcid=y[1].upper())
        if y := re.search(r'DOI:\s*"?(10\.[^"\s]+)', q, re.I):
            return Source("paper", doi=y[1])
        return Source("paper")  # a preprint (SRC:PPR) or another record of Europe PMC's: the paper's id is in the table
    if x := m(r"https?://(?:www\.)?europepmc\.org/(?:api/getPdf\?pmcid=|backend/ptpmcrender\.fcgi\?accid=|articles?/(?:PMC/)?|abstract/PMC/)(PMC\d+)(/bin/)?"):
        return Source("supplement", u, pmcid=x[1].upper()) if x[2] else Source("paper", pmcid=x[1].upper())
    if x := m(r"https?://(?:www\.)?europepmc\.org/(?:abstract|article)/MED/(\d+)"):
        return Source("paper", pmid=x[1])
    if m(r"https?://(?:www\.)?europepmc\.org/"):
        return Source("paper")
    # PMC, PubMed, BioC, E-utilities
    if x := m(r"https?://(?:pmc\.ncbi\.nlm\.nih\.gov|www\.ncbi\.nlm\.nih\.gov/pmc)/articles/instance/(\d+)/bin/"):
        return Source("supplement", u, pmcid="PMC" + x[1])
    if x := m(r"https?://(?:pmc\.ncbi\.nlm\.nih\.gov|www\.ncbi\.nlm\.nih\.gov/pmc)/articles/(?:PMC)?(\d+)(/bin/)?"):
        return Source("supplement", u, pmcid="PMC" + x[1]) if x[2] else Source("paper", pmcid="PMC" + x[1])
    if x := m(r"https?://(?:pubmed\.ncbi\.nlm\.nih\.gov|www\.ncbi\.nlm\.nih\.gov/pubmed)/(\d+)"):
        return Source("paper", pmid=x[1])
    if x := m(r"https?://www\.ncbi\.nlm\.nih\.gov/research/bionlp/RESTful/pmcoa\.cgi/BioC_\w+/(PMC)?(\d+)/"):
        return Source("paper", pmcid="PMC" + x[2]) if x[1] else Source("paper", pmid=x[2])
    if x := m(r"https?://eutils\.ncbi\.nlm\.nih\.gov/entrez/eutils/e\w+\.fcgi\?(.*)"):
        q = urllib.parse.parse_qs(x[1])
        db, i = q.get("db", [""])[0], q.get("id", [""])[0]
        if db == "pubmed":
            return Source("paper", pmid=i)
        if db == "pmc":
            return Source("paper", pmcid="PMC" + i.removeprefix("PMC"))
        if db == "bioproject":
            return Source("record", f"https://www.ncbi.nlm.nih.gov/bioproject/{i}")
        return Source("website", u)
    # DOIs
    if x := m(r"https?://(?:dx\.)?doi\.org/(10\.[^?#]+)") or m(r"https?://api\.datacite\.org/dois/(10\.[^?#]+)"):
        return Source("doi", doi=_q(x[1]))
    # supplementary files
    if x := m(r"https?://(?:media\.springernature\.com/[^/]+/springer-static|static-content\.springer\.com)/esm/"
              r"art%3A(10\.\d+%2F[^/]+?)(?:%2F|/)MediaObjects(?:%2F|/)([^/?#]+)"):
        return Source("supplement", f"https://static-content.springer.com/esm/art%3A{x[1]}/MediaObjects/{x[2]}", doi=_q(x[1]))
    if x := m(r"https?://ars\.els-cdn\.com/content/image/1-s2\.0-(S[0-9X]+)-"):
        return Source("supplement", u, pii=x[1])
    if x := m(r"https?://onlinelibrary\.wiley\.com/action/downloadSupplement\?doi=([^&]+)"):
        return Source("supplement", u, doi=_q(x[1]))
    if x := m(r"https?://www\.(?:medrxiv|biorxiv)\.org/content/(?:medrxiv|biorxiv)/early/\d{4}/\d\d/\d\d/(\d{4}\.\d\d\.\d\d\.\d+)/DC\d+/embed/"):
        return Source("supplement", u, doi="10.1101/" + x[1])
    if x := m(r"https?://journals\.plos\.org/\w+/article/file\?(?:[^#]*&)?id=(10\.1371/[^&#]+?)\.s\d+"):
        return Source("supplement", u, doi=_q(x[1]))
    if x := m(r"https?://www\.ahajournals\.org/doi/suppl/(10\.\d+/[^/]+)/suppl_file/"):
        return Source("supplement", u, doi=_q(x[1]))
    if SUPPLEMENTS.match(u):
        return Source("supplement", u)
    # preprints: the DOI is in the address, or, for a preprint posted before 2026 (when the servers' DOIs moved from
    # the prefix 10.1101), it is 10.1101/ and the preprint's number
    if x := m(r"https?://www\.(?:medrxiv|biorxiv)\.org/content/(10\.\d+/(?:\d{4}\.\d\d\.\d\d\.\d+|\d{6}))"):
        return Source("preprint", doi=x[1])
    if x := m(r"https?://www\.(?:medrxiv|biorxiv)\.org/content/(?:(?:medrxiv|biorxiv)/)?early/\d{4}/\d\d/\d\d/((\d{4})\.\d\d\.\d\d\.\d+|\d{6})"):
        return Source("preprint", doi="10.1101/" + x[1]) if not x[2] or x[2] < "2026" else Source("website", u)
    # records
    for pattern, page in RECORDS:
        if x := m(pattern):
            return Source("record", page.format(x[1]))
    # publishers' pages
    if x := m(r"https?://www\.nature\.com/articles/([\w.-]+?)(?:\.pdf)?(?:[/?#]|$)"):
        return Source("paper", doi="10.1038/" + x[1], guess=True)
    if x := m(r"https?://www\.sciencedirect\.com/science/article/(?:abs/)?pii/(S[0-9X]+)") or m(r"https?://www\.(?:cell|thelancet)\.com/.*?(?:PII)?(S[0-9X]{4}-?[0-9X]{4}\(\d\d\)[0-9X]{5}-[0-9X])"):
        return Source("paper", pii=re.sub(r"[()-]", "", x[1]))
    if PUBLISHED.match(u):
        d = re.search(r"(10\.\d{4,9}/[^?#&\s]+?)(?:/full|/abstract|/pdf|\.pdf)?(?:[?#&]|$)", _q(u))
        return Source("paper", doi=d[1] if d else "")
    return Source("website", u)


def cite(paper, read_at, copies=True):
    """The oboInOwl:hasDbXref values for one quote, from its table's PMID cell (PMID:n or DOI:...) and its read-at
    address (several, separated by |, when a fact rests on more than one document). An address that is the paper
    itself is not cited; nor, with `copies`, is a website when the row names a paper, since it is then a copy of the
    paper. A paper read at an address with no PMID in the table is cited by the address, which the source-form check
    reports."""
    out = [paper] if paper else []
    for a in [a.strip() for a in (read_at or "").split("|") if a.strip()]:
        s = classify(a)
        if s.kind == "paper":
            add = [] if paper else [a]
        elif s.kind == "doi":
            add = [] if paper else [f"DOI:{s.doi}"]
        elif s.kind == "preprint":
            add = [f"DOI:{s.doi}"]
        elif s.kind == "website":
            add = [] if paper and copies else [s.url]
        else:
            add = [s.url]
        out += [x for x in add if x.lower() not in {y.lower() for y in out}]
    return out


def cite_sources(value):
    """A definition's sources (IAO:0000119, separated by |) in the cited forms: identifiers as they are, addresses as
    cite() gives them."""
    out = []
    for part in [p.strip() for p in (value or "").split("|") if p.strip()]:
        out += [x for x in (cite("", part) if part.startswith("http") else [part]) if x.lower() not in {y.lower() for y in out}]
    return out


# ---------------------------------------------------------------- filling the PMID column

PMC_IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def get_json(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "coho-sources"}), timeout=120) as r:
                return json.load(r)
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"lookup failed: {url[:120]}")


def by_pmcid(pmcids):
    """PMC id -> (PMID, DOI), from PMC's ID converter."""
    out, ids = {}, sorted(set(pmcids))
    for i in range(0, len(ids), 150):
        j = get_json(PMC_IDCONV + "?" + urllib.parse.urlencode({"ids": ",".join(ids[i:i + 150]), "format": "json", "tool": "coho-sources"}))
        for r in j.get("records", []):
            if r.get("pmcid"):
                out[r["pmcid"]] = (str(r.get("pmid") or ""), r.get("doi") or "")
    return out


def by_doi(dois):
    """DOI (lower case) -> PMID, from Europe PMC."""
    out, ids = {}, sorted({d.lower() for d in dois if not re.search(r'[\s"]', d)})
    for i in range(0, len(ids), 40):
        q = " OR ".join(f'DOI:"{d}"' for d in ids[i:i + 40])
        j = get_json(EUROPEPMC + "?" + urllib.parse.urlencode({"query": q, "format": "json", "resultType": "lite", "pageSize": 1000}))
        for r in j["resultList"]["result"]:
            if r.get("doi") and r.get("pmid"):
                out[r["doi"].lower()] = r["pmid"]
        time.sleep(0.3)
    return out


def by_pii(piis):
    """Elsevier PII -> DOI, from Crossref."""
    out = {}
    for p in sorted(set(piis)):
        items = get_json("https://api.crossref.org/works?" + urllib.parse.urlencode({"filter": f"alternative-id:{p}", "rows": 2}))["message"]["items"]
        if len(items) == 1:
            out[p] = items[0]["DOI"]
        time.sleep(0.3)
    return out


def resolve(urls):
    """address -> PMID:n, or DOI:... for a paper without a PMID, for every address that identifies its paper."""
    cs = {u: classify(u) for u in urls}
    # a preprint is left to cite(), which adds its own DOI; a DOI link without a PMID is cited by its DOI
    cs = {u: s for u, s in cs.items() if s.kind in ("paper", "supplement", "doi") and (s.pmid or s.pmcid or s.doi or s.pii)}
    pii = by_pii(s.pii for s in cs.values() if s.pii)
    pmc = by_pmcid(s.pmcid for s in cs.values() if s.pmcid and not s.pmid)

    def doi_of(s):
        return s.doi or pii.get(s.pii, "") or pmc.get(s.pmcid, ("", ""))[1]

    doi = by_doi(doi_of(s) for s in cs.values() if not (s.pmid or pmc.get(s.pmcid, ("", ""))[0]) and doi_of(s))
    out = {}
    for u, s in cs.items():
        d = doi_of(s)
        pmid = s.pmid or pmc.get(s.pmcid, ("", ""))[0] or doi.get(d.lower(), "")
        if pmid:
            out[u] = f"PMID:{pmid}"
        elif d and s.kind != "doi" and not s.guess:
            out[u] = f"DOI:{d}"
    return out


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="\t"))


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter="\t", lineterminator="\n").writerows(rows)


SUBLINK = re.compile(r'^(ObjectPropertyAssertion\()((?:Annotation\((?:[^()"]|"(?:[^"\\]|\\.)*")*\) )+)(coho:isSubCohortOf coho:COHO_\d+ coho:COHO_\d+\))$')
XREF = re.compile(r'Annotation\(oboInOwl:hasDbXref "((?:[^"\\]|\\.)*)"\) ?')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--check", action="store_true", help="also fail on a row whose PMID is not the paper of its address")
    a = ap.parse_args()
    tables = {t: read_rows(CUR / t) for t in TABLES if (CUR / t).exists()}
    cols = {t: (rows[0].index("PMID"), rows[0].index("read at")) for t, rows in tables.items()}
    definitions = read_rows(CUR / "definitions_curated.tsv")
    s = definitions[0].index("source")
    edit = M.EDIT.read_text(encoding="utf-8").split("\n")

    def cell(row, i):
        return row[i].strip() if len(row) > i else ""

    def split(value):
        return [x.strip() for x in value.split("|") if x.strip()]

    # the addresses to resolve: those of empty or DOI cells (of every row, with --check), of the definitions' sources
    # and of the sub-cohort links; and the DOIs given, which become PMIDs once PubMed indexes the paper
    want, dois = set(), set()
    for t, rows in tables.items():
        p, r = cols[t]
        for row in rows[1:]:
            cur = cell(row, p)
            if a.check or not cur or cur.startswith("DOI:"):
                want |= set(split(cell(row, r)))
            if cur.startswith("DOI:"):
                dois.add(cur[4:])
    for row in definitions[1:]:
        want |= {x for x in split(cell(row, s)) if x.startswith("http")}
        dois |= {x[4:] for x in split(cell(row, s)) if x.startswith("DOI:")}
    for line in edit:
        if SUBLINK.match(line):
            want |= {M.unesc(x) for x in XREF.findall(line) if x.startswith("http")}
    ids = resolve(want)
    indexed = {f"DOI:{d}".lower(): f"PMID:{p}" for d, p in by_doi(dois).items()}
    filled, left, wrong = {}, {}, []
    for t, rows in tables.items():
        p, r = cols[t]
        for n, row in enumerate(rows[1:], 2):
            if len(row) <= r:
                continue
            got = [ids[x] for x in split(row[r]) if x in ids and classify(x).kind != "preprint"]
            cur = row[p].strip()
            if cur.lower() in indexed:
                got = [indexed[cur.lower()]]
            if got and (not cur or cur.startswith("DOI:") and got[0].startswith("PMID:") and cur != got[0]):
                row[p] = got[0]  # an empty cell filled, or a DOI given its paper's PMID once PubMed has one
                filled[t] = filled.get(t, 0) + 1
            elif cur:
                # a PMID is compared with the address's PMID, a DOI with its DOI (a DOI PubMed lacks says nothing)
                if a.check and got and cur not in got and any(g.split(":")[0] == cur.split(":")[0] for g in got):
                    wrong.append(f"{t}:{n} {row[0]} gives {cur} but {row[r][:90]} is {', '.join(got)}")
            elif any(classify(x).kind in ("paper", "supplement") for x in split(row[r])):
                left.setdefault(t, []).append(f"{n} {row[0]} {row[r][:110]}")
    # definitions' sources: a paper's address becomes its PMID, a supplement keeps its file beside its paper's PMID
    cited = 0
    for row in definitions[1:]:
        parts = split(cell(row, s))
        if not parts:
            continue
        new = []
        for x in parts:
            k = classify(x).kind if x.startswith("http") else ""
            if x.lower() in indexed:
                new.append(indexed[x.lower()])
            elif k in ("paper", "doi") and x in ids:
                new.append(ids[x])
            elif k == "supplement" and x in ids:
                new += [ids[x], x]
            else:
                new.append(x)
        new = list(dict.fromkeys(new))
        if new != parts:
            row[s] = "|".join(new)
            cited += 1
    # the sub-cohort links of the edit file: cited as the tables' quotes are
    linked = 0
    for i, line in enumerate(edit):
        mm = SUBLINK.match(line)
        if not mm:
            continue
        xs = [M.unesc(x) for x in XREF.findall(mm[2])]
        paper = next((x for x in xs if PAPER_ID.match(x)), "") or next((ids[x] for x in xs if x in ids and classify(x).kind != "preprint"), "")
        new = cite(paper, "|".join(x for x in xs if x.startswith("http")))
        if new != xs:
            rest = XREF.sub("", mm[2]).strip()
            anns = " ".join(([rest] if rest else []) + [f'Annotation(oboInOwl:hasDbXref "{M.esc(x)}")' for x in new])
            edit[i] = f"{mm[1]}{anns} {mm[3]}"
            linked += 1
    for t, n in filled.items():
        print(f"{t}: {n} PMID cells filled")
    print(f"definitions_curated.tsv: {cited} sources cited by PMID; coho-edit.owl: {linked} sub-cohort links cited by PMID")
    for t, xs in left.items():
        print(f"{t}: {len(xs)} quotes read in a paper with no PMID or DOI found:\n  " + "\n  ".join(xs))
    if wrong:
        print(f"{len(wrong)} rows whose PMID is not the paper of their address:\n  " + "\n  ".join(wrong))
    if not a.dry_run:
        for t, rows in tables.items():
            write_rows(CUR / t, rows)
        write_rows(CUR / "definitions_curated.tsv", definitions)
        M.EDIT.write_text("\n".join(edit), encoding="utf-8")
    if wrong:
        sys.exit(1)


if __name__ == "__main__":
    main()
