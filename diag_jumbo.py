import re
import requests

url = "https://www.jumbocolombia.com/arroz-diana-x-5-kg/p"
r = requests.get(url, headers={"User-Agent": "MercadoOptimoBot/0.1 (proyecto academico)"}, timeout=20)
print("estado:", r.status_code)
print("URL final:", r.url)
print("tamaño:", len(r.text))
print("bloques ld+json:", len(re.findall(r'application/ld\+json', r.text)))
print("título:", re.findall(r"<title>(.*?)</title>", r.text, re.S)[:1])
open("jumbo_raw.html", "w", encoding="utf-8").write(r.text)
