import ts from 'typescript';
import { describe, expect, it } from 'vitest';

import core from './es/core.json';
import features from './es/features.json';

/**
 * i18n como requisito (2026-11-25): todo texto visible sale de `es/*.json` y cada clave del JSON se usa.
 * Analiza el código de la app (sin tests ni el cliente generado) con el compilador de TypeScript.
 */
const SOURCES = import.meta.glob(
  ['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!../test/**', '!../api/schema.d.ts', '!../**/*.d.ts'],
  { query: '?raw', import: 'default', eager: true },
) as Record<string, string>;

/** Literales visibles permitidos fuera de `t()`, siempre con su motivo. Clave: `fichero|literal`. */
const ALLOWED_LITERALS: Readonly<Record<string, string>> = {
  '../features/context/ContextPage.tsx|es': 'código de idioma ISO de ejemplo, no texto',
  '../features/context/QualityPage.tsx|doc-organize-classify': 'alias de modelo del proxy, no texto',
};

/** Atributos JSX y propiedades de objeto que llegan a la pantalla o a un lector de pantalla. */
const VISIBLE_ATTRIBUTES = new Set([
  'aria-label',
  'aria-description',
  'aria-valuetext',
  'title',
  'placeholder',
  'label',
  'description',
  'alt',
  'error',
  'message',
]);
const VISIBLE_PROPERTIES = new Set(['title', 'message', 'label', 'description', 'placeholder']);
const HAS_WORDS = /[A-Za-zÁÉÍÓÚáéíóúÑñÜü]{2,}/;
const PLURAL = /_(zero|one|two|few|many|other)$/;

function flatten(value: unknown, prefix = '', out = new Set<string>()): Set<string> {
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      flatten(child, prefix ? `${prefix}.${key}` : key, out);
    }
  } else {
    out.add(prefix);
  }
  return out;
}

const KEYS = [...flatten(core), ...flatten(features)];
const KEY_SET = new Set(KEYS);
const keyExists = (key: string) =>
  KEY_SET.has(key) ||
  KEYS.some((candidate) => candidate.replace(PLURAL, '') === key || candidate.startsWith(`${key}.`));

const isTranslateCall = (node: ts.CallExpression, file: ts.SourceFile) =>
  /(^|\.)t$/.test(node.expression.getText(file));

interface Analysis {
  visible: string[];
  missing: string[];
  dynamicWithoutKeys: string[];
  literals: Set<string>;
  dynamicPrefixes: Set<string>;
}

function analyse(): Analysis {
  const result: Analysis = {
    visible: [],
    missing: [],
    dynamicWithoutKeys: [],
    literals: new Set(),
    dynamicPrefixes: new Set(),
  };
  for (const [path, text] of Object.entries(SOURCES)) {
    const file = ts.createSourceFile(
      path,
      text,
      ts.ScriptTarget.Latest,
      true,
      path.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const where = (node: ts.Node) =>
      `${path}:${file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1}`;
    const insideTranslate = (node: ts.Node) => {
      for (let parent = node.parent; parent; parent = parent.parent) {
        if (ts.isCallExpression(parent) && isTranslateCall(parent, file)) {
          return true;
        }
      }
      return false;
    };
    // Un literal que es una clave (p. ej. el `message` de un esquema zod) se traduce al mostrarse con `t(message)`.
    const reportVisible = (node: ts.Node, literal: string, label: string) => {
      if (
        HAS_WORDS.test(literal) &&
        !KEY_SET.has(literal) &&
        !insideTranslate(node) &&
        !(`${path}|${literal}` in ALLOWED_LITERALS)
      ) {
        result.visible.push(`${where(node)} ${label}${JSON.stringify(literal)}`);
      }
    };
    const checkKeyArgument = (node: ts.Expression) => {
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        if (!keyExists(node.text)) {
          result.missing.push(`${where(node)} ${node.text}`);
        }
      } else if (ts.isTemplateExpression(node)) {
        const prefix = node.head.text;
        result.dynamicPrefixes.add(prefix);
        if (prefix && !KEYS.some((key) => key.startsWith(prefix))) {
          result.dynamicWithoutKeys.push(`${where(node)} ${node.getText(file)}`);
        }
      } else if (ts.isConditionalExpression(node)) {
        checkKeyArgument(node.whenTrue);
        checkKeyArgument(node.whenFalse);
      }
      // Otras expresiones (una variable con la clave) se cubren por los literales: la clave aparece escrita en algún sitio.
    };
    const visit = (node: ts.Node) => {
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        result.literals.add(node.text);
      }
      if (ts.isCallExpression(node) && isTranslateCall(node, file) && node.arguments[0]) {
        checkKeyArgument(node.arguments[0]);
      }
      if (ts.isJsxText(node)) {
        reportVisible(node, node.text.trim(), '');
      }
      if (ts.isJsxAttribute(node) && node.initializer && VISIBLE_ATTRIBUTES.has(node.name.getText(file))) {
        const value = ts.isJsxExpression(node.initializer) ? node.initializer.expression : node.initializer;
        if (value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))) {
          reportVisible(node, value.text, `${node.name.getText(file)}=`);
        }
      }
      if (
        ts.isPropertyAssignment(node) &&
        VISIBLE_PROPERTIES.has(node.name.getText(file).replace(/['"]/g, '')) &&
        (ts.isStringLiteral(node.initializer) || ts.isNoSubstitutionTemplateLiteral(node.initializer))
      ) {
        reportVisible(node, node.initializer.text, `${node.name.getText(file)}: `);
      }
      ts.forEachChild(node, visit);
    };
    visit(file);
  }
  return result;
}

const ANALYSIS = analyse();

describe('i18n', () => {
  it('analiza el código de la app', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(50);
    expect(KEYS.length).toBeGreaterThan(500);
  });

  it('ningún texto visible queda fuera de t()', () => {
    expect(ANALYSIS.visible).toEqual([]);
  });

  it('cada clave que usa el código existe en es/*.json', () => {
    expect(ANALYSIS.missing).toEqual([]);
    expect(ANALYSIS.dynamicWithoutKeys).toEqual([]);
  });

  it('cada clave de es/*.json se usa', () => {
    const unused = KEYS.filter((key) => {
      const base = key.replace(PLURAL, '');
      if (ANALYSIS.literals.has(base) || ANALYSIS.literals.has(key)) {
        return false;
      }
      return ![...ANALYSIS.dynamicPrefixes].some((prefix) => prefix && base.startsWith(prefix));
    });
    expect(unused).toEqual([]);
  });

  it('cada excepción permitida sigue existiendo', () => {
    const stale = Object.keys(ALLOWED_LITERALS).filter((entry) => {
      const [path = '', literal = ''] = entry.split('|');
      return !SOURCES[path]?.includes(`"${literal}"`);
    });
    expect(stale).toEqual([]);
  });
});
