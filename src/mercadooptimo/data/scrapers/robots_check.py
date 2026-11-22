"""Revisión de robots.txt de las cadenas candidatas.

Uso:
    mercadooptimo check-robots
    mercadooptimo check-robots --out robots_report.md

Descarga el robots.txt de cada cadena y reporta, con el user-agent del
proyecto, si se pueden consultar las rutas de ejemplo. No descarga páginas de
productos. Los términos de uso hay que leerlos a mano (se imprimen los enlaces).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from mercadooptimo.data.scrapers.base import USER_AGENT
from mercadooptimo.data.scrapers.robots import RobotsPolicy


@dataclass
class Chain:
    name: str
    root: str
    sample_paths: list[str] = field(default_factory=lambda: [
        "/", "/producto-ejemplo/p", "/api/catalog_system/pub/products/search", "/busca/arroz",
        "/categoria?sort=price", "/categoria?page=2"])
    terms_url: str = ""


# Ajustar dominios/rutas si cambian. Los términos se verifican manualmente.
CHAINS = [
    Chain("exito", "https://www.exito.com", terms_url="https://www.exito.com/terminos-condiciones"),
    Chain("jumbo", "https://www.jumbocolombia.com", terms_url="https://www.jumbocolombia.com/institucional/terminos-y-condiciones"),
    Chain("olimpica", "https://www.olimpica.com"),
    Chain("d1", "https://domicilios.tiendasd1.com"),
]


def check_chain(chain: Chain, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    out = {"chain": chain.name, "url": f"{chain.root}/robots.txt", "terms": chain.terms_url}
    try:
        resp = session.get(out["url"], timeout=15)
    except requests.RequestException as exc:
        out.update(status=f"error de red: {exc}", paths={}, crawl_delay=None, text="")
        return out
    out["status"] = resp.status_code
    out["text"] = resp.content.decode("utf-8", errors="replace") if resp.ok else ""
    rp = RobotsPolicy(out["text"], USER_AGENT) if resp.ok else RobotsPolicy.deny_all(USER_AGENT)
    out["crawl_delay"] = rp.crawl_delay()
    out["paths"] = {p: rp.can_fetch(chain.root + p) for p in chain.sample_paths}
    return out


def render(results: list[dict]) -> str:
    lines = ["# Revisión de robots.txt", f"User-agent usado: `{USER_AGENT}`", ""]
    for r in results:
        lines += [f"## {r['chain']}", f"- robots.txt: {r['url']} -> estado {r['status']}"]
        if r["terms"]:
            lines.append(f"- Términos de uso (revisar a mano): {r['terms']}")
        lines.append(f"- Crawl-delay declarado: {r['crawl_delay']}")
        for path, ok in r["paths"].items():
            lines.append(f"- {path}: {'PERMITIDO' if ok else 'BLOQUEADO'}")
        if r["text"]:
            lines += ["", "```", r["text"].strip()[:4000], "```"]
        lines.append("")
    return "\n".join(lines)


def run(out_path: str | None = None) -> None:
    text = render([check_chain(c) for c in CHAINS])
    print(text)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\nReporte guardado en {out_path}")
