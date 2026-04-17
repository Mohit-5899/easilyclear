"""Tests for the source whitelist gate (ARCHITECTURE.md §10.1)."""

import pytest

from ingestion.source_whitelist import (
    AllowedSource,
    SourceNotAllowedError,
    get_publisher,
    is_allowed,
    validate_source,
)

ALLOWED_URLS = [
    "https://ncert.nic.in/textbook/pdf/jess3dd.zip",
    "https://www.ncert.nic.in/textbook.php?jess3=0-7",
    "https://rajeduboard.rajasthan.gov.in/books/class10.pdf",
    "https://NCERT.NIC.IN/something.pdf",
    "http://ncert.nic.in/textbook/pdf/chapter1.pdf",
]

DISALLOWED_URLS = [
    "https://vedantu.com/ncert-solutions/class-10.pdf",
    "https://byjus.com/class-10/geography/",
    "https://utkarsh.com/downloads/ncert-class10.pdf",
    "https://testbook.com/live-coaching/ras",
    "https://scribd.com/doc/12345/ncert-class-10-geography",
    "https://t.me/exams_rajasthan/123",
    "https://gist.github.com/anonymous/123",
]


def test_allowed_urls() -> None:
    for url in ALLOWED_URLS:
        assert is_allowed(url) is True, f"expected allowed: {url}"
        # validate_source must not raise for whitelisted sources.
        source = validate_source(url)
        assert isinstance(source, AllowedSource)
        assert source.authority == "official"


def test_disallowed_urls() -> None:
    for url in DISALLOWED_URLS:
        assert is_allowed(url) is False, f"expected disallowed: {url}"
        with pytest.raises(SourceNotAllowedError):
            get_publisher(url)
        with pytest.raises(SourceNotAllowedError):
            validate_source(url)


def test_validate_source_returns_correct_metadata() -> None:
    ncert = validate_source("https://ncert.nic.in/textbook/pdf/jess3dd.zip")
    assert ncert.publisher == "NCERT"
    assert ncert.authority == "official"
    assert ncert.domain == "ncert.nic.in"

    # www. prefix must be stripped during domain comparison.
    ncert_www = validate_source("https://www.ncert.nic.in/textbook.php?jess3=0-7")
    assert ncert_www.publisher == "NCERT"
    assert ncert_www.domain == "ncert.nic.in"

    # Uppercase domain must match case-insensitively.
    ncert_upper = validate_source("https://NCERT.NIC.IN/something.pdf")
    assert ncert_upper.publisher == "NCERT"
    assert ncert_upper.domain == "ncert.nic.in"

    rbse = validate_source("https://rajeduboard.rajasthan.gov.in/books/class10.pdf")
    assert rbse.publisher == "RBSE"
    assert rbse.authority == "official"
    assert rbse.domain == "rajeduboard.rajasthan.gov.in"
