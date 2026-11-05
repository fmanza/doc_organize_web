import { Group, Pagination, Select, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatCount } from './format';
import { PAGE_SIZES, type PageState } from './usePageState';

interface PageControlsProps {
  state: PageState;
  total: number;
  /** Nombre del listado para los lectores de pantalla («Páginas de documentos»). */
  label: string;
  /** Sin selector de tamaño (listados con tamaño fijo). */
  fixedSize?: boolean;
}

/** «1–25 de 1 234», paginación y tamaño de página; no pinta nada si todo cabe en la primera página. */
export function PageControls({ state, total, label, fixedSize = false }: PageControlsProps) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  // Todo cabe en una página: sin controles, salvo que la URL apunte a otra página (vieja o a mano), para poder volver.
  if (total <= (fixedSize ? state.pageSize : PAGE_SIZES[0]) && state.page === 1) {
    return null;
  }
  const first = Math.min(total, state.offset + 1);
  const last = Math.min(total, state.offset + state.pageSize);
  return (
    <Group justify="space-between" gap="sm">
      <Text size="sm" c="dimmed">
        {t('paging.range', { first: formatCount(first), last: formatCount(last), total: formatCount(total) })}
      </Text>
      <Group gap="sm">
        <Pagination
          total={pages}
          value={Math.min(state.page, pages)}
          onChange={state.setPage}
          size="sm"
          siblings={1}
          getControlProps={(control) => ({
            'aria-label': t(`paging.${control}`),
          })}
          getItemProps={(page) => ({ 'aria-label': t('paging.page', { page }) })}
          aria-label={label}
        />
        {!fixedSize && (
          <Select
            aria-label={t('paging.size')}
            size="xs"
            w={110}
            allowDeselect={false}
            value={String(state.pageSize)}
            onChange={(value) => value && state.setPageSize(Number(value))}
            data={PAGE_SIZES.map((size) => ({ value: String(size), label: t('paging.perPage', { size }) }))}
          />
        )}
      </Group>
    </Group>
  );
}
