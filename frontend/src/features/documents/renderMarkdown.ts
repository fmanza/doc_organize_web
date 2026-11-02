import DOMPurify from 'dompurify';
import { marked } from 'marked';

/**
 * Markdown convertido → HTML seguro para el visor. El Markdown viene de documentos de terceros: puede llevar HTML,
 * scripts o enlaces a cualquier sitio, así que:
 *
 * - `marked` lo convierte y DOMPurify quita todo lo ejecutable (scripts, eventos `on*`, `javascript:`), además de
 *   estilos, formularios, marcos, SVG y MathML;
 * - las imágenes relativas (`img/<stem>/p1.png`, como las escribe doc_organize) se piden al visor de la API; las
 *   externas o `data:` se quitan (no se hacen peticiones a otros sitios al abrir un documento);
 * - los enlaces externos abren en otra pestaña sin `opener`; los demás dejan de ser enlaces.
 */
export function renderMarkdown(markdown: string, imageUrl: (relative: string) => string | null): string {
  const html = marked.parse(markdown, { async: false, gfm: true });
  const fragment = DOMPurify.sanitize(html, {
    RETURN_DOM_FRAGMENT: true,
    FORBID_TAGS: [
      'style',
      'form',
      'input',
      'button',
      'iframe',
      'object',
      'embed',
      'svg',
      'math',
      'video',
      'audio',
    ],
    FORBID_ATTR: ['style', 'srcset'],
  });
  for (const img of Array.from(fragment.querySelectorAll('img'))) {
    const src = img.getAttribute('src') ?? '';
    const url = isRelative(src) ? imageUrl(decodeSafe(src)) : null;
    if (url) {
      img.setAttribute('src', url);
      img.setAttribute('loading', 'lazy');
    } else {
      img.replaceWith(document.createTextNode(img.getAttribute('alt') ?? ''));
    }
  }
  for (const link of Array.from(fragment.querySelectorAll('a'))) {
    const href = link.getAttribute('href') ?? '';
    if (/^https?:\/\//i.test(href)) {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    } else if (!href.startsWith('#')) {
      link.removeAttribute('href');
    }
  }
  // Documento inerte: los <img> no empiezan a cargarse hasta que React inserta el HTML.
  const container = document.implementation.createHTMLDocument('').createElement('div');
  container.append(container.ownerDocument.importNode(fragment, true));
  return container.innerHTML;
}

function isRelative(src: string): boolean {
  return src !== '' && !src.startsWith('/') && !/^[a-z][a-z0-9+.-]*:/i.test(src);
}

function decodeSafe(src: string): string {
  try {
    return decodeURI(src);
  } catch {
    return src;
  }
}

/** `relative` (con `..` o `.`) junto al fichero `base`; `null` si se sale de la raíz. */
export function joinRelative(base: string, relative: string): string | null {
  const parts = base.split('/').slice(0, -1);
  for (const part of relative.split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') {
      if (parts.length === 0) return null;
      parts.pop();
    } else {
      parts.push(part);
    }
  }
  return parts.join('/');
}
