# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=protected-access

"""Tests for qutebrowser.utils.urlutils."""

import collections

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.commands import cmdexc
from qutebrowser.utils import utils, urlutils


class FakeDNS:

    """Helper class for the fake_dns fixture."""

    FakeDNSAnswer = collections.namedtuple('FakeDNSAnswer', ['error'])

    def __init__(self):
        self.reset()

    def __repr__(self):
        return utils.get_repr(self, used=self.used, answer=self.answer)

    def reset(self):
        self.used = False
        self.answer = None

    def _get_error(self):
        return not self.answer

    def fromname_mock(self, _host):
        if self.answer is None:
            raise ValueError("Got called without answer being set. This means "
                             "something tried to make an unexpected DNS "
                             "request (QHostInfo::fromName).")
        if self.used:
            raise ValueError("Got used twice!.")
        self.used = True
        return self.FakeDNSAnswer(error=self._get_error)


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Patched QHostInfo.fromName to catch DNS requests.

    With autouse=True so accidental DNS requests get discovered because the
    fromname_mock will be called without answer being set.
    """
    dns = FakeDNS()
    monkeypatch.setattr('qutebrowser.utils.urlutils.QHostInfo.fromName',
                        dns.fromname_mock)
    return dns


@pytest.fixture(autouse=True)
def urlutils_config_stub(config_stub, monkeypatch):
    """Initialize the given config_stub.

    Args:
        stub: The ConfigStub provided by the config_stub fixture.
        auto_search: The value auto-search should have.
    """
    config_stub.data = {
        'general': {'auto-search': True},
        'searchengines': {
            'test': 'http://www.qutebrowser.org/?q={}',
            'DEFAULT': 'http://www.example.com/?q={}',
        },
    }
    monkeypatch.setattr('qutebrowser.utils.urlutils.config', config_stub)
    return config_stub


@pytest.fixture
def urlutils_message_mock(message_mock):
    message_mock.patch('qutebrowser.utils.urlutils.message')
    return message_mock


@pytest.mark.parametrize('url, special', [
    ('file:///tmp/foo', True),
    ('about:blank', True),
    ('qute:version', True),
    ('http://www.qutebrowser.org/', False),
    ('www.qutebrowser.org', False),
])
def test_special_urls(url, special):
    u = QUrl(url)
    assert urlutils.is_special_url(u) == special


@pytest.mark.parametrize('url, host, query', [
    ('testfoo', 'www.example.com', 'q=testfoo'),
    ('test testfoo', 'www.qutebrowser.org', 'q=testfoo'),
    ('test testfoo bar foo', 'www.qutebrowser.org', 'q=testfoo bar foo'),
    ('test testfoo ', 'www.qutebrowser.org', 'q=testfoo'),
    ('!python testfoo', 'www.example.com', 'q=%21python testfoo'),
    ('blub testfoo', 'www.example.com', 'q=blub testfoo'),
])
def test_get_search_url(urlutils_config_stub, url, host, query):
    """Tests for _get_search_url."""
    url = urlutils._get_search_url(url)
    assert url.host() == host
    assert url.query() == query


@pytest.mark.parametrize('is_url, is_url_no_autosearch, uses_dns, url', [
    # Normal hosts
    (True, True, False, 'http://foobar'),
    (True, True, False, 'localhost:8080'),
    (True, True, True, 'qutebrowser.org'),
    (True, True, True, ' qutebrowser.org '),
    (True, True, False, 'http://user:password@example.com/foo?bar=baz#fish'),
    # IPs
    (True, True, False, '127.0.0.1'),
    (True, True, False, '::1'),
    (True, True, True, '2001:41d0:2:6c11::1'),
    (True, True, True, '94.23.233.17'),
    # Special URLs
    (True, True, False, 'file:///tmp/foo'),
    (True, True, False, 'about:blank'),
    (True, True, False, 'qute:version'),
    (True, True, False, 'localhost'),
    # _has_explicit_scheme False, special_url True
    (True, True, False, 'qute::foo'),
    # Invalid URLs
    (False, True, False, ''),
    (False, True, False, 'http:foo:0'),
    # Not URLs
    (False, True, False, 'foo bar'),  # no DNS because of space
    (False, True, False, 'localhost test'),  # no DNS because of space
    (False, True, False, 'another . test'),  # no DNS because of space
    (False, True, True, 'foo'),
    (False, True, False, 'this is: not an URL'),  # no DNS because of space
    (False, True, False, '23.42'),  # no DNS because bogus-IP
    (False, True, False, '1337'),  # no DNS because bogus-IP
    (False, True, True, 'deadbeef'),
    (False, True, False, '31c3'),  # no DNS because bogus-IP
    (False, True, False, 'foo::bar'),  # no DNS because of no host
    # Valid search term with autosearch
    (False, False, False, 'test foo'),
    # autosearch = False
    (False, True, False, 'This is an URL without autosearch'),
])
def test_is_url(urlutils_config_stub, fake_dns, is_url, is_url_no_autosearch,
                uses_dns, url):
    urlutils_config_stub.data['general']['auto-search'] = 'dns'
    if uses_dns:
        fake_dns.answer = True
        result = urlutils.is_url(url)
        assert fake_dns.used
        assert result
        fake_dns.reset()

        fake_dns.answer = False
        result = urlutils.is_url(url)
        assert fake_dns.used
        assert not result
    else:
        result = urlutils.is_url(url)
        assert not fake_dns.used
        assert result == is_url

    fake_dns.reset()
    urlutils_config_stub.data['general']['auto-search'] = 'naive'
    assert urlutils.is_url(url) == is_url
    assert not fake_dns.used

    fake_dns.reset()
    urlutils_config_stub.data['general']['auto-search'] = False
    assert urlutils.is_url(url) == is_url_no_autosearch
    assert not fake_dns.used


@pytest.mark.parametrize('user_input, output', [
    ('qutebrowser.org', 'http://qutebrowser.org'),
    ('http://qutebrowser.org', 'http://qutebrowser.org'),
    ('::1/foo', 'http://[::1]/foo'),
    ('[::1]/foo', 'http://[::1]/foo'),
    ('http://[::1]', 'http://[::1]'),
    ('qutebrowser.org', 'http://qutebrowser.org'),
    ('http://qutebrowser.org', 'http://qutebrowser.org'),
    ('::1/foo', 'http://[::1]/foo'),
    ('[::1]/foo', 'http://[::1]/foo'),
    ('http://[::1]', 'http://[::1]'),
])
def test_qurl_from_user_input(user_input, output):
    url = urlutils.qurl_from_user_input(user_input)
    assert url.toString() == output


@pytest.mark.parametrize('url, valid, has_err_string', [
    ('http://www.example.com/', True, False),
    ('', False, False),
    ('://', False, True),
])
def test_invalid_url_error(urlutils_message_mock, url, valid, has_err_string):
    """Tests for invalid_url_error."""
    qurl = QUrl(url)
    assert qurl.isValid() == valid
    if valid:
        with pytest.raises(ValueError):
            urlutils.invalid_url_error(0, qurl, '')
        assert not urlutils_message_mock.messages
    else:
        assert bool(qurl.errorString()) == has_err_string
        urlutils.invalid_url_error(0, qurl, 'frozzle')

        msg = urlutils_message_mock.getmsg()
        assert msg.win_id == 0
        assert msg.immediate == False
        if has_err_string:
            expected_text = ("Trying to frozzle with invalid URL - " +
                             qurl.errorString())
        else:
            expected_text = "Trying to frozzle with invalid URL"
        assert msg.text == expected_text


@pytest.mark.parametrize('url, valid, has_err_string', [
    ('http://www.example.com/', True, False),
    ('', False, False),
    ('://', False, True),
])
def test_raise_cmdexc_if_invalid(url, valid, has_err_string):
    """Tests for raise_cmdexc_if_invalid."""
    qurl = QUrl(url)
    assert qurl.isValid() == valid
    if valid:
        urlutils.raise_cmdexc_if_invalid(qurl)
    else:
        assert bool(qurl.errorString()) == has_err_string
        with pytest.raises(cmdexc.CommandError) as excinfo:
            urlutils.raise_cmdexc_if_invalid(qurl)
        if has_err_string:
            expected_text = "Invalid URL - " + qurl.errorString()
        else:
            expected_text = "Invalid URL"
        assert str(excinfo.value) == expected_text


@pytest.mark.parametrize('qurl, output', [
    (QUrl(), None),
    (QUrl('http://qutebrowser.org/test.html'), 'test.html'),
    (QUrl('http://qutebrowser.org/foo.html#bar'), 'foo.html'),
    (QUrl('http://user:password@qutebrowser.org/foo?bar=baz#fish'), 'foo'),
    (QUrl('http://qutebrowser.org/'), 'qutebrowser.org.html'),
    (QUrl('qute://'), None),
])
def test_filename_from_url(qurl, output):
    assert urlutils.filename_from_url(qurl) == output


@pytest.mark.parametrize('qurl, tpl', [
    (QUrl(), None),
    (QUrl('qute://'), None),
    (QUrl('qute://foobar'), None),
    (QUrl('mailto:nobody'), None),
    (QUrl('ftp://example.com/'),
        ('ftp', 'example.com', 21)),
    (QUrl('ftp://example.com:2121/'),
        ('ftp', 'example.com', 2121)),
    (QUrl('http://qutebrowser.org:8010/waterfall'),
        ('http', 'qutebrowser.org', 8010)),
    (QUrl('https://example.com/'),
        ('https', 'example.com', 443)),
    (QUrl('https://example.com:4343/'),
        ('https', 'example.com', 4343)),
    (QUrl('http://user:password@qutebrowser.org/foo?bar=baz#fish'),
        ('http', 'qutebrowser.org', 80)),
])
def test_host_tuple(qurl, tpl):
    if tpl is None:
        with pytest.raises(ValueError):
            urlutils.host_tuple(qurl)
    else:
        assert urlutils.host_tuple(qurl) == tpl


@pytest.mark.parametrize('url, raising, has_err_string', [
    (None, False, False),
    (QUrl(), False, False),
    (QUrl('http://www.example.com/'), True, False),
])
def test_fuzzy_url_error(url, raising, has_err_string):
    """Tests for FuzzyUrlError."""
    if raising:
        expected_exc = ValueError
    else:
        expected_exc = urlutils.FuzzyUrlError

    with pytest.raises(expected_exc) as excinfo:
        raise urlutils.FuzzyUrlError("Error message", url)

    if not raising:
        if has_err_string:
            expected_text = "Error message: " + qurl.errorString()
        else:
            expected_text = "Error message"
        assert str(excinfo.value) == expected_text
