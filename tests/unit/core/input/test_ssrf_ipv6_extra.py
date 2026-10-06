"""
Additional SSRF coverage for IPv6 address families not exercised by the
upstream suite: unique-local (fc00::/7), IPv4-mapped IPv6 (::ffff:0:0/96)
and redirects / GET-only paths that land on them.
"""

import socket
from unittest.mock import Mock, patch

import pytest
import requests

from docling_graph.core.input.handlers import URLInputHandler
from docling_graph.core.input.validators import URLValidator
from docling_graph.exceptions import ValidationError


def _addrinfo(*ips: str) -> list:
    """Build a socket.getaddrinfo-style result list for the given IP addresses."""
    return [
        (socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))
        for ip in ips
    ]


BLOCKED_IPV6 = [
    "fc00::1",  # unique local
    "fd12:3456:789a::1",  # unique local
    "fe80::1%eth0",  # scoped link-local, as getaddrinfo may return it
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
    "::ffff:10.0.0.5",  # IPv4-mapped RFC 1918
    "::ffff:172.16.0.1",
    "::ffff:192.168.1.1",
    "::ffff:169.254.169.254",  # IPv4-mapped cloud metadata
    "::",  # unspecified
]


class TestIPv6Blocking:
    @pytest.fixture
    def validator(self):
        return URLValidator()

    @pytest.mark.parametrize("ip", BLOCKED_IPV6)
    @patch("socket.getaddrinfo")
    def test_validator_blocks_hostname_resolving_to_ipv6(self, mock_getaddrinfo, validator, ip):
        mock_getaddrinfo.return_value = _addrinfo(ip)
        with pytest.raises(ValidationError, match="not allowed"):
            validator.validate("https://innocent.example.com/doc.pdf")

    @pytest.mark.parametrize("ip", BLOCKED_IPV6)
    @patch("socket.getaddrinfo")
    def test_handler_blocks_before_any_request(self, mock_getaddrinfo, ip):
        mock_getaddrinfo.return_value = _addrinfo(ip)
        with patch("requests.head") as mock_head, patch("requests.get") as mock_get:
            with pytest.raises(ValidationError, match="not allowed"):
                URLInputHandler().load("https://innocent.example.com/doc.pdf")
            mock_head.assert_not_called()
            mock_get.assert_not_called()

    @patch("socket.getaddrinfo")
    def test_public_dual_stack_host_allowed(self, mock_getaddrinfo, validator):
        mock_getaddrinfo.return_value = _addrinfo("93.184.216.34", "2606:2800:220:1::1")
        validator.validate("https://example.com/doc.pdf")


class TestRedirectToIPv6:
    @patch("socket.getaddrinfo")
    @patch("requests.head")
    @patch("requests.get")
    def test_head_redirect_to_ipv4_mapped_metadata_blocked(
        self, mock_get, mock_head, mock_getaddrinfo
    ):
        mock_getaddrinfo.side_effect = [
            _addrinfo("93.184.216.34"),
            _addrinfo("::ffff:169.254.169.254"),
        ]
        redirect = Mock(status_code=302, headers={"Location": "http://[::ffff:a9fe:a9fe]/latest/"})
        mock_head.return_value = redirect

        with pytest.raises(ValidationError, match="not allowed"):
            URLInputHandler().load("https://attacker.example/redirect")
        mock_get.assert_not_called()

    @patch("socket.getaddrinfo")
    @patch("requests.head")
    @patch("requests.get")
    def test_get_only_redirect_to_ula_blocked_when_head_fails(
        self, mock_get, mock_head, mock_getaddrinfo
    ):
        """If HEAD errors out, redirects on the GET path must still be validated per hop."""
        mock_getaddrinfo.side_effect = [_addrinfo("93.184.216.34"), _addrinfo("fd00::10")]
        mock_head.side_effect = requests.ConnectionError("HEAD not supported")
        mock_get.return_value = Mock(status_code=301, headers={"Location": "http://internal/"})

        with pytest.raises(ValidationError, match="not allowed"):
            URLInputHandler().load("https://attacker.example/redirect")

        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs["allow_redirects"] is False

    @patch("socket.getaddrinfo")
    @patch("requests.head")
    @patch("requests.get")
    def test_requests_never_auto_follow_redirects(self, mock_get, mock_head, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _addrinfo("93.184.216.34")
        mock_head.return_value = Mock(status_code=200, headers={"content-type": "text/plain"})
        ok = Mock(status_code=200, headers={"content-type": "text/plain"})
        ok.iter_content.return_value = [b"hello"]
        mock_get.return_value = ok

        path = URLInputHandler().load("https://example.com/file.txt")
        try:
            assert path.read_bytes() == b"hello"
        finally:
            path.unlink()

        assert mock_head.call_args.kwargs["allow_redirects"] is False
        assert mock_get.call_args.kwargs["allow_redirects"] is False
