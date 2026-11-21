"""Base para la recolección de precios de portales de comercio electrónico.

Cada cadena se implementa como una subclase de `StoreScraper` (o se configura
con `SelectorScraper` si la página es estática). La clase base:

* consulta robots.txt y se niega a descargar rutas no permitidas;
* espacia las peticiones (`delay` segundos) para no sobrecargar el sitio;
* devuelve filas con el esquema de la tabla `prices`.

Antes de activar una cadena se deben revisar sus términos de uso. Para
páginas que se renderizan con JavaScript, implementar `fetch_html` con
Playwright en la subclase.
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from mercadooptimo.data.scrapers.robots import RobotsPolicy

USER_AGENT = "MercadoOptimoBot/0.1 (proyecto academico)"


class StoreScraper(ABC):
    store: str = "tienda"

    def __init__(self, delay: float = 2.0, session: requests.Session | None = None):
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, RobotsPolicy] = {}
        self._last_request = 0.0

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            try:
                resp = self.session.get(urljoin(root, "/robots.txt"), timeout=10)
            except requests.RequestException:
                # Sin respuesta no sabemos qué permite el sitio: no se descarga nada.
                policy = RobotsPolicy.deny_all(USER_AGENT)
            else:
                if resp.ok:
                    policy = RobotsPolicy(resp.content.decode("utf-8", errors="replace"), USER_AGENT)
                elif resp.status_code in (404, 410):
                    policy = RobotsPolicy.allow_all(USER_AGENT)  # no publica robots.txt
                else:
                    # 401/403/5xx: acceso denegado o sitio caído; ser conservador.
                    policy = RobotsPolicy.deny_all(USER_AGENT)
            self._robots[root] = policy
        return self._robots[root].can_fetch(url)

    def fetch_html(self, url: str) -> str:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt no permite descargar {url}")
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=20)
        self._last_request = time.monotonic()
        resp.raise_for_status()
        return resp.text

    @abstractmethod
    def scrape(self) -> pd.DataFrame:
        """Devuelve un DataFrame con columnas product_id, store, date, price, source."""


def parse_cop(text: str) -> float | None:
    """'$ 14.500' -> 14500.0 ; '$14.500,50' -> 14500.5"""
    m = re.search(r"\d[\d.\s]*(,\d+)?", text or "")
    if not m:
        return None
    num = m.group(0).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


@dataclass
class ProductPage:
    product_id: str
    url: str
    price_selector: str  # selector CSS del precio en la página del producto


class SelectorScraper(StoreScraper):
    """Scraper configurable para páginas estáticas: una URL y un selector por producto."""

    def __init__(self, store: str, pages: list[ProductPage], **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self.pages = pages

    def scrape(self) -> pd.DataFrame:
        today = date.today().isoformat()
        rows = []
        for page in self.pages:
            try:
                html = self.fetch_html(page.url)
            except (requests.RequestException, PermissionError) as exc:
                print(f"[{self.store}] {page.product_id}: {exc}")
                continue
            node = BeautifulSoup(html, "html.parser").select_one(page.price_selector)
            price = parse_cop(node.get_text()) if node else None
            if price:
                rows.append((page.product_id, self.store, today, price, "scraping"))
        return pd.DataFrame(rows, columns=["product_id", "store", "date", "price", "source"])
