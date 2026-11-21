"""Política de robots.txt para los scrapers.

Se usa Protego (RFC 9309: comodines `*` y `$`, grupos bien delimitados) en lugar de
`urllib.robotparser`, que no entiende comodines y descarta las reglas que siguen a una
línea en blanco.

Además se aplica una política CONSERVADORA: algunos sitios (p. ej. Éxito) escriben sus
`Disallow` bajo el grupo de otro bot, de modo que leídos al pie de la letra no aplicarían
a `*`. Aquí una ruta solo se considera permitida si lo permite (1) el grupo que nos
corresponde y (2) el conjunto de TODAS las reglas Disallow del archivo, sin importar el
grupo. Es más estricto que la lectura literal, a propósito.
"""

from __future__ import annotations

from protego import Protego


def _merged_rules(text: str) -> str:
    """Un robots.txt sintético con todos los Disallow (y los Allow específicos) del archivo."""
    lines = ["User-agent: *"]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "disallow" and value:
            lines.append(f"Disallow: {value}")
        elif key == "allow" and value not in ("", "/", "/*"):
            lines.append(f"Allow: {value}")
    return "\n".join(lines)


class RobotsPolicy:
    def __init__(self, text: str, user_agent: str):
        self.user_agent = user_agent
        self._own = Protego.parse(text)
        self._merged = Protego.parse(_merged_rules(text))

    @classmethod
    def deny_all(cls, user_agent: str) -> "RobotsPolicy":
        return cls("User-agent: *\nDisallow: /", user_agent)

    @classmethod
    def allow_all(cls, user_agent: str) -> "RobotsPolicy":
        return cls("", user_agent)

    def can_fetch(self, url: str) -> bool:
        return bool(self._own.can_fetch(url, self.user_agent) and self._merged.can_fetch(url, self.user_agent))

    def crawl_delay(self) -> float | None:
        return self._own.crawl_delay(self.user_agent)
