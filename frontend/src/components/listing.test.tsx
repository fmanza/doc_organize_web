import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../test/render';
import { SearchBox } from './listing';

describe('SearchBox', () => {
  it('muestra la etiqueta «Buscar» y conserva el nombre accesible específico', () => {
    renderWithProviders(<SearchBox value="" onChange={vi.fn()} label="Buscar ubicaciones" />);

    expect(screen.getByText('Buscar', { selector: 'label' })).toBeVisible();
    const input = screen.getByRole('textbox', { name: 'Buscar ubicaciones' });
    expect(input).toHaveAttribute('placeholder', 'Buscar ubicaciones');
    expect(screen.queryByRole('button', { name: 'Limpiar la búsqueda' })).not.toBeInTheDocument();
  });

  it('el aspa vacía el campo y avisa sin esperar', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<SearchBox value="acta" onChange={onChange} label="Buscar ubicaciones" />);

    const clear = screen.getByRole('button', { name: 'Limpiar la búsqueda' });
    // Mantine pone `pointer-events: none` en la sección derecha salvo que se pida lo contrario.
    expect(clear.closest('[data-position="right"]')).not.toHaveStyle({ pointerEvents: 'none' });
    await user.click(clear);

    expect(screen.getByRole('textbox', { name: 'Buscar ubicaciones' })).toHaveValue('');
    expect(onChange).toHaveBeenCalledWith('');
  });
});
