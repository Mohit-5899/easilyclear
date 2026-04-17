"""Source whitelist enforcement for textbook ingestion.

Only official publishers are permitted as PDF sources. This module is the
single gate every ingestion call must pass through. See ARCHITECTURE.md §10.1
and CLAUDE.md §3.1 for the policy rationale.
"""

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl

WHITELIST: dict[str, str] = {
    "ncert.nic.in": "NCERT",
    "rajeduboard.rajasthan.gov.in": "RBSE",
}


class AllowedSource(BaseModel):
    """Validated, whitelisted textbook source."""

    url: HttpUrl
    publisher: str
    authority: Literal["official"]
    domain: str


class SourceNotAllowedError(ValueError):
    """Raised when a URL is not from a whitelisted official publisher."""

    def __init__(self, url: str, domain: str | None = None) -> None:
        allowed = ", ".join(sorted(WHITELIST.keys()))
        where = f" (domain: {domain})" if domain else ""
        super().__init__(
            f"Source not allowed: {url}{where}. "
            f"Only these official publishers are permitted: {allowed}."
        )
        self.url = url
        self.domain = domain


def _normalize_domain(url: str) -> str:
    """Extract a lowercase netloc with any leading 'www.' stripped."""
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def is_allowed(url: str) -> bool:
    """Return True if the URL's domain is in the whitelist."""
    return _normalize_domain(url) in WHITELIST


def get_publisher(url: str) -> str:
    """Return the publisher name for a whitelisted URL.

    Raises:
        SourceNotAllowedError: if the URL's domain is not whitelisted.
    """
    domain = _normalize_domain(url)
    publisher = WHITELIST.get(domain)
    if publisher is None:
        raise SourceNotAllowedError(url, domain or None)
    return publisher


def validate_source(url: str) -> AllowedSource:
    """Validate a URL against the whitelist and return a typed source record.

    This is the main entry point for the ingestion pipeline. Callers should
    catch SourceNotAllowedError and surface a clear rejection message.

    Raises:
        SourceNotAllowedError: if the URL's domain is not whitelisted.
    """
    domain = _normalize_domain(url)
    publisher = WHITELIST.get(domain)
    if publisher is None:
        raise SourceNotAllowedError(url, domain or None)
    return AllowedSource(
        url=url,
        publisher=publisher,
        authority="official",
        domain=domain,
    )
