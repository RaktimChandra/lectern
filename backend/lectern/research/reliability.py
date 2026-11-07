"""Source reliability scoring.

The score is a transparent heuristic, not a verdict: each source gets a tier and
the reasons behind it, and QC Layer 1 reports them so an instructor can see why
a source was trusted or flagged. Standards bodies and official documentation
outrank tutorials and community posts because they are the authority that
everything else paraphrases.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..models import Reliability, SourceKind

PRIMARY = {
    "rfc-editor.org": "IETF RFC (the published standard)",
    "datatracker.ietf.org": "IETF standards tracker",
    "ietf.org": "Internet Engineering Task Force",
    "w3.org": "World Wide Web Consortium standard",
    "whatwg.org": "WHATWG living standard",
    "ecma-international.org": "Ecma International standard",
    "iso.org": "ISO standard",
    "nist.gov": "US National Institute of Standards and Technology",
    "unicode.org": "Unicode Consortium",
}

OFFICIAL_DOCS = {
    "developer.mozilla.org": "MDN Web Docs (maintained reference for web platform)",
    "docs.python.org": "Official Python documentation",
    "python.org": "Python Software Foundation",
    "learn.microsoft.com": "Microsoft official documentation",
    "docs.oracle.com": "Oracle official documentation",
    "docs.aws.amazon.com": "AWS official documentation",
    "cloud.google.com": "Google Cloud official documentation",
    "developers.google.com": "Google developer documentation",
    "web.dev": "Google web.dev guidance",
    "react.dev": "Official React documentation",
    "nodejs.org": "Official Node.js documentation",
    "git-scm.com": "Official Git documentation",
    "kubernetes.io": "Official Kubernetes documentation",
    "docs.docker.com": "Official Docker documentation",
    "postgresql.org": "Official PostgreSQL documentation",
    "dev.mysql.com": "Official MySQL documentation",
    "typescriptlang.org": "Official TypeScript documentation",
    "go.dev": "Official Go documentation",
    "doc.rust-lang.org": "Official Rust documentation",
    "pytorch.org": "Official PyTorch documentation",
    "tensorflow.org": "Official TensorFlow documentation",
    "scikit-learn.org": "Official scikit-learn documentation",
    "docs.github.com": "Official GitHub documentation",
    "cloudflare.com": "Cloudflare learning centre / documentation",
    "httpwg.org": "HTTP Working Group (IETF)",
}

ACADEMIC_SUFFIXES = (".edu", ".ac.uk", ".ac.in", ".ac.jp", ".edu.au")
ACADEMIC = {
    "arxiv.org": "arXiv preprint (not peer reviewed by default)",
    "acm.org": "ACM digital library",
    "dl.acm.org": "ACM digital library",
    "ieee.org": "IEEE",
    "ieeexplore.ieee.org": "IEEE Xplore",
    "nature.com": "Nature",
    "springer.com": "Springer",
    "nptel.ac.in": "NPTEL (IIT course material)",
    "ocw.mit.edu": "MIT OpenCourseWare",
}

REFERENCE = {
    "wikipedia.org": "Wikipedia (useful overview; verify against primary sources)",
    "britannica.com": "Encyclopaedia Britannica",
}

PUBLISHER = {
    "oreilly.com": "O'Reilly Media",
    "manning.com": "Manning Publications",
    "realpython.com": "Real Python (edited tutorials)",
    "freecodecamp.org": "freeCodeCamp (community-edited)",
    "digitalocean.com": "DigitalOcean community tutorials (edited)",
    "ibm.com": "IBM",
    "redhat.com": "Red Hat",
    "khanacademy.org": "Khan Academy",
    "coursera.org": "Coursera",
}

COMMUNITY = {
    "stackoverflow.com": "Stack Overflow (community answers; quality varies)",
    "medium.com": "Medium (self-published)",
    "dev.to": "DEV Community (self-published)",
    "hashnode.dev": "Hashnode (self-published)",
    "geeksforgeeks.org": "GeeksforGeeks (tutorial site; known accuracy issues)",
    "w3schools.com": "W3Schools (tutorial site; simplified)",
    "tutorialspoint.com": "Tutorialspoint (tutorial site)",
    "javatpoint.com": "Javatpoint (tutorial site)",
    "quora.com": "Quora (user answers)",
    "reddit.com": "Reddit (user discussion)",
    "blogspot.com": "Blogspot (self-published)",
}

RESPECTED_BOOK_PUBLISHERS = (
    "o'reilly", "oreilly", "manning", "addison", "pearson", "prentice", "mit press", "no starch",
    "pragmatic", "apress", "wiley", "packt", "springer", "cambridge", "oxford", "mcgraw",
)

TIER_SCORES = {
    "primary": 0.97,
    "official_docs": 0.9,
    "academic": 0.85,
    "publisher": 0.72,
    "reference": 0.7,
    "community": 0.45,
    "unknown": 0.5,
}


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _match(host: str, table: dict[str, str]) -> str | None:
    for domain, reason in table.items():
        if host == domain or host.endswith("." + domain):
            return reason
    return None


def assess(url: str, kind: SourceKind, *, publisher: str = "", view_count: int | None = None,
           has_transcript: bool = False, authoritative_domains: list[str] | None = None) -> Reliability:
    host = domain_of(url)
    reasons: list[str] = []

    if kind == "book":
        pub = publisher.lower()
        if any(p in pub for p in RESPECTED_BOOK_PUBLISHERS):
            return Reliability(tier="publisher", score=0.8, reasons=[f"Published by {publisher}", "Bibliographic record, not full text"])
        reasons = [f"Publisher: {publisher}" if publisher else "Publisher unknown", "Bibliographic record, not full text"]
        return Reliability(tier="publisher" if publisher else "unknown", score=0.62 if publisher else 0.5, reasons=reasons)

    if kind == "video":
        score = 0.5
        reasons.append("Video: check the presenter before relying on it")
        if has_transcript:
            score += 0.08
            reasons.append("Transcript available, so its content could be checked")
        if view_count and view_count > 100_000:
            score += 0.07
            reasons.append(f"Widely viewed ({view_count:,} views)")
        return Reliability(tier="community", score=round(min(score, 0.7), 2), reasons=reasons)

    if kind == "instructor":
        reasons.append("Supplied by the instructor")

    for table, tier in ((PRIMARY, "primary"), (OFFICIAL_DOCS, "official_docs"), (ACADEMIC, "academic"),
                        (REFERENCE, "reference"), (PUBLISHER, "publisher"), (COMMUNITY, "community")):
        reason = _match(host, table)
        if reason:
            reasons.append(reason)
            return Reliability(tier=tier, score=TIER_SCORES[tier], reasons=reasons)

    if host.endswith(ACADEMIC_SUFFIXES):
        return Reliability(tier="academic", score=TIER_SCORES["academic"], reasons=[*reasons, "Academic institution domain"])
    if host.endswith(".gov") or ".gov." in host:
        return Reliability(tier="official_docs", score=0.88, reasons=[*reasons, "Government domain"])
    if host.startswith(("docs.", "developer.", "developers.")):
        return Reliability(tier="official_docs", score=0.82, reasons=[*reasons, "Documentation subdomain"])
    if authoritative_domains and any(host == d or host.endswith("." + d) for d in authoritative_domains):
        return Reliability(tier="official_docs", score=0.8, reasons=[*reasons, "Identified as authoritative for this topic during research planning"])

    return Reliability(tier="unknown", score=TIER_SCORES["unknown"], reasons=[*reasons, "No reputation data for this site"])
