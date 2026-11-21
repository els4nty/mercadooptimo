import pytest
import requests

from mercadooptimo.data.scrapers.base import SelectorScraper


class FakeResp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.ok = 200 <= status < 400


class FakeSession:
    def __init__(self, resp=None, exc=None):
        self.headers = {}
        self.resp, self.exc = resp, exc

    def get(self, url, timeout=None):
        if self.exc:
            raise self.exc
        return self.resp


def scraper(session):
    return SelectorScraper("x", [], session=session, delay=0)


def test_robots_disallow_se_respeta():
    s = scraper(FakeSession(FakeResp(200, "User-agent: *\nDisallow: /privado")))
    assert not s.allowed("https://t.co/privado/a")
    assert s.allowed("https://t.co/producto/a")


def test_robots_inexistente_permite():
    assert scraper(FakeSession(FakeResp(404))).allowed("https://t.co/p")


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_robots_inaccesible_bloquea(status):
    assert not scraper(FakeSession(FakeResp(status))).allowed("https://t.co/p")


def test_robots_error_de_red_bloquea():
    assert not scraper(FakeSession(exc=requests.ConnectionError())).allowed("https://t.co/p")
