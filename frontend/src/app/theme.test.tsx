import { NumberInput, Select, TextInput } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Providers } from './Providers';

/**
 * Regla del proyecto (frontend.instructions.md): etiqueta, campo, descripción. Con la descripción debajo, los campos
 * de una misma fila de un formulario de varias columnas quedan alineados aunque sus ayudas tengan distinta longitud.
 */
describe('tema: orden de etiqueta, campo y descripción', () => {
  it('la descripción va debajo del campo en todos los tipos de campo', () => {
    render(
      <Providers env="test">
        <TextInput label="Texto" description="Ayuda del texto" />
        <NumberInput label="Número" description="Ayuda del número" />
        <Select label="Opción" description="Ayuda de la opción" data={['a']} />
      </Providers>,
    );

    for (const [name, help] of [
      ['Texto', 'Ayuda del texto'],
      ['Número', 'Ayuda del número'],
      ['Opción', 'Ayuda de la opción'],
    ] as const) {
      const field = screen.getByLabelText(name, { selector: 'input' });
      const label = screen.getByText(name);
      const description = screen.getByText(help);
      expect(label.compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(field.compareDocumentPosition(description) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      // La descripción sigue asociada al campo para los lectores de pantalla.
      expect(field).toHaveAccessibleDescription(help);
    }
  });
});
