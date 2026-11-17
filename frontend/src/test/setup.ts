import '@testing-library/jest-dom/vitest';
import '../i18n';

import { cleanup, configure } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// `findBy*` y `waitFor` esperan 1 s por defecto. La primera pantalla de cada test carga su ruta en diferido y las
// traducciones de `features.json`: en una máquina cargada (CI, o Docker con los workers en marcha) pasa del segundo y
// fallaban tests distintos en cada ejecución. 5 s solo alargan un test que de verdad falla.
configure({ asyncUtilTimeout: 5000 });

// jsdom no implementa matchMedia ni ResizeObserver, que Mantine usa.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverStub;
// Los desplegables de Mantine desplazan la opción activa a la vista.
Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
