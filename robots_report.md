# Revisión de robots.txt
User-agent usado: `MercadoOptimoBot/0.1 (proyecto academico)`

## exito
- robots.txt: https://www.exito.com/robots.txt -> estado 200
- Términos de uso (revisar a mano): https://www.exito.com/terminos-condiciones
- Crawl-delay declarado: None
- /: PERMITIDO
- /producto-ejemplo/p: PERMITIDO
- /api/catalog_system/pub/products/search: BLOQUEADO
- /busca/arroz: PERMITIDO
- /categoria?sort=price: BLOQUEADO
- /categoria?page=2: PERMITIDO

```
# Cloudflare Content Signals
User-agent: *
Content-Signal: search=yes, ai-train=no
Allow: /

# Google Ads bots (necesarios para medición y anuncios)
User-agent: AdsBot-Mobile-Web-Android
Allow: /

User-agent: AdsBot-Mobile-Web
Allow: /

# IA / LLMs
User-agent: GPTBot
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Applebot-Extended
Allow: /

# Áreas privadas / no indexables
Disallow: /account/
Disallow: /login
Disallow: /checkout/
Disallow: /quick-view/
Disallow: /espiar/

# Búsqueda interna
Disallow: /s?

# Facetas y ordenamientos (NO rastreables)
Disallow: /*?*facets=
Disallow: /*?*sort=
Disallow: /*?*category-

# Paginación (SÍ rastreable)
Allow: /*?page=

# APIs
Disallow: /api/

# Colecciones no SEO
Disallow: /coleccion/

# Sitemaps
Sitemap: https://www.exito.com/sitemap/sitemap.xml
Sitemap: https://www.exito.com/friendly-collections.xml
```

## jumbo
- robots.txt: https://www.tiendasjumbo.co/robots.txt -> estado error de red: HTTPSConnectionPool(host='www.tiendasjumbo.co', port=443): Max retries exceeded with url: /robots.txt (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1010)')))
- Términos de uso (revisar a mano): https://www.jumbocolombia.com/institucional/terminos-y-condiciones
- Crawl-delay declarado: None

## olimpica
- robots.txt: https://www.olimpica.com/robots.txt -> estado 200
- Crawl-delay declarado: None
- /: PERMITIDO
- /producto-ejemplo/p: PERMITIDO
- /api/catalog_system/pub/products/search: PERMITIDO
- /busca/arroz: BLOQUEADO
- /categoria?sort=price: BLOQUEADO
- /categoria?page=2: BLOQUEADO

```
# Disallow all crawlers access to certain pages. 
User-agent: *
Disallow: /secret 
Disallow: /*?orderFormId=
Allow: /*.css
Allow: /*.jpeg
Allow: /*.js
Allow: /*.png
Allow: /*.webp
Allow: /*.jpg
Allow: /*.svg
Allow: /*.woff
Allow: /*.gif
Allow: /*.ico

User-agent: *
Disallow: /*&
Disallow: /*%

Sitemap: https://www.olimpica.com/sitemap.xml

User-agent: Googlebot
Allow: /*
Disallow: /*?orderFormId=
Disallow: *?itm_*
Disallow: /account/*
Disallow: /login/*
Disallow: /checkout/*
Disallow: /busca/*
Disallow: /quick-view/*
Disallow: /espiar/*
Disallow: /buscapagina/*
Disallow: *?utm*
Disallow: *productLinkNotFound*
Disallow: *?msvid*
Disallow: *?order=OrderBy*
Disallow: /search?_query=*
Allow: *?idsku=*
Allow: *?skuid=*
Allow: /*?page=

User-agent: Google-Extended
Allow: /*
Disallow: /*?orderFormId=
Disallow: *?itm_*
Disallow: /img/*
Disallow: /account/*
Disallow: /login/*
Disallow: /checkout/*
Disallow: /busca/*
Disallow: /quick-view/*
Disallow: /espiar/*
Disallow: /buscapagina/*
Disallow: *?utm*
Disallow: *productLinkNotFound*
Disallow: *?msvid*
Disallow: *?order=OrderBy*
Disallow: /search?_query=*
Allow: *?idsku=*
Allow: *?skuid=*

User-agent: Googlebot-Image
Allow: /*
Disallow: /*?orderFormId=
Disallow: *?itm_*
Disallow: /img/*
Disallow: /account/*
Disallow: /login/*
Disallow: /checkout/*
Disallow: /busca/*
Disallow: /quick-view/*
Disallow: /espiar/*
Disallow: /buscapagina/*
Disallow: *?utm*
Disallow: *productLinkNotFound*
Disallow: *?msvid*
Disallow: *?order=OrderBy*
Disallow: /search?_query=*

Disallow: /Site/Servicos.aspx 
Disallow: /Site/TagsMaisPopulares.aspx 
Disallow: /Site/QuickView.aspx 
Disallow: /Site/Produto_Listas.aspx 
Disallow: /Site/ProdutoFrete.aspx 
Disallow: /Site/TagDetalhe.aspx
```

## d1
- robots.txt: https://domicilios.tiendasd1.com/robots.txt -> estado 200
- Crawl-delay declarado: None
- /: PERMITIDO
- /producto-ejemplo/p: PERMITIDO
- /api/catalog_system/pub/products/search: PERMITIDO
- /busca/arroz: BLOQUEADO
- /categoria?sort=price: PERMITIDO
- /categoria?page=2: PERMITIDO

```
# Disallow all crawlers access to certain pages. 

User-agent: *

# =================================================================
# ALLOWS (Permitir rastreo de recursos críticos (CSS, JS, Imágenes))
# Esto es vital para que Google renderice la página correctamente.
# =================================================================

Allow: /*.css$
Allow: /*.js$
Allow: /*.jpg$
Allow: /*.jpeg$
Allow: /*.png$
Allow: /*.gif$
Allow: /*.svg$


# =================================================================
# DISALLOWS (Bloqueo de Rutas Privadas o de bajo valor SEO)
# =================================================================

Disallow: /account/*
Disallow: /login/*
Disallow: /checkout/*
Disallow: /busca/*
Disallow: /quick-view/*
Disallow: /espiar/*
Disallow: /buscapagina/*

# =================================================================
# DISALLOWS (Bloqueo de Query Strings de VTEX y Seguimiento)
# El asterisco (*) inicial bloquea el parámetro en cualquier parte de la URL.
# =================================================================

Disallow: *initialMap=
Disallow: *initialQuery=
Disallow: *map=
Disallow: *searchState=
Disallow: *sc=
Disallow: *riode=
Disallow: *workspace=
Disallow: *q=*&map=
Disallow: *OrderBy=
Disallow: *srlid=
Disallow: *utm_source= 
Disallow: *utm_medium=
Disallow: *utm_campaign=


# UBICACIÓN DEL SITEMAP
Sitemap: https://www.d1.com.co/sitemap.xml
```
