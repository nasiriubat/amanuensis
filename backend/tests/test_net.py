import pytest

from app.net import UnsafeUrlError, assert_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x.pdf",
        "https://127.0.0.1/x.pdf",
        "http://10.0.0.5/x.pdf",
        "http://192.168.1.10/x.pdf",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/x.pdf",
        "https://[fd00::1]/x.pdf",  # unique-local IPv6
        "ftp://example.com/x.pdf",  # non-http scheme
        "http:///x.pdf",  # no host
    ],
)
def test_rejects_non_public_or_bad_scheme(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(url)


def test_allows_public_literal_ip():
    # 8.8.8.8 is a global address; no DNS needed, so this stays offline-safe.
    assert_public_url("https://8.8.8.8/paper.pdf")
