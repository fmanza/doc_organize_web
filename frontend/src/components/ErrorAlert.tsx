import { Alert, type AlertProps } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';
import { problemTitle } from './problem';

interface ErrorAlertProps extends Omit<AlertProps, 'title' | 'children'> {
  error: unknown;
}

/** Muestra el *problem details* de un `ApiError` (título y detalle), nunca trazas. */
export function ErrorAlert({ error, ...props }: ErrorAlertProps) {
  const { t } = useTranslation();
  // Título en el idioma de la interfaz; sin *problem details* (p. ej. un 502 del proxy) lo pone i18n.
  const title = error instanceof ApiError ? problemTitle(error.problem, t) : t('common.error');
  const detail = error instanceof ApiError ? error.problem.detail : t('common.errorBody');
  return (
    <Alert color="red" role="alert" title={title} {...props}>
      {detail}
    </Alert>
  );
}
