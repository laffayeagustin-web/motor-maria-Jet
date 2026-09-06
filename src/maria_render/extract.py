"""Extractores del DOM renderizado — los `page.evaluate()` que alimentan el bundle.

Consolidados de `docs/prototipo/prueba_indice.py` y `geo_probe.py`. Cada constante
es un snippet JS que corre en el contexto de la página ya renderizada.

Criterio de texto (D3, principio de simetría): `textContent` tras remover
script/style/noscript/template, texto oculto por CSS incluido — igual que
`maria_common.text.raw_text_content` en el lado servido.
"""
from __future__ import annotations

JS_TEXT_CONTENT = """() => {
  const b = document.body ? document.body.cloneNode(true) : null;
  if (!b) return '';
  b.querySelectorAll('script,style,noscript,template').forEach(n => n.remove());
  return b.textContent || '';
}"""

JS_LD_BLOCKS = """() => Array.from(
  document.querySelectorAll('script[type="application/ld+json"]')
).map(s => s.textContent)"""

JS_MODEL_CONTEXT = """() => {
  try {
    const mc = navigator.modelContext;
    if (!mc) return { present: false, tools: 0 };
    let tools = 0;
    if (Array.isArray(mc.tools)) tools = mc.tools.length;
    else if (typeof mc.listTools === 'function') {
      const t = mc.listTools();
      tools = Array.isArray(t) ? t.length : 0;
    }
    return { present: true, tools };
  } catch (e) { return { present: false, tools: 0 }; }
}"""

JS_FORMS = """() => Array.from(document.querySelectorAll('form')).map(f => ({
  fields: f.querySelectorAll(
    'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]), select, textarea'
  ).length,
  required: f.querySelectorAll('[required], [aria-required=\"true\"]').length
}))"""

JS_QUOTE_LINK = r"""() => {
  const rx = /cotiz|presupuest|quote|reserv[aá]|solicit|contact/i;
  return Array.from(document.querySelectorAll('a[href]')).some(
    a => rx.test(a.textContent || '') || rx.test(a.getAttribute('href') || '')
  );
}"""

JS_PRICE_ON_SCREEN = r"""() => {
  const t = document.body ? document.body.innerText : '';
  return /(US\$|U\$S|USD|EUR|€|\$)\s?\d{2,}/.test(t);
}"""

JS_NAV_LINKS_INTERNAL = """() => {
  const host = location.hostname.replace(/^www\\./, '');
  let n = 0;
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('mailto:') ||
        href.startsWith('tel:') || href.startsWith('javascript:')) continue;
    if (href.startsWith('/') || href.includes(host)) n++;
  }
  return n;
}"""

JS_FOOTER_LINKS = """() => {
  const foot = document.querySelector('footer') || document.body;
  if (!foot) return [];
  return Array.from(foot.querySelectorAll('a[href]')).map(a => ({
    text: (a.textContent || '').trim().slice(0, 80),
    href: a.getAttribute('href') || ''
  })).filter(l => l.href && !l.href.startsWith('#'));
}"""
