import { Alert, type AlertProps } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';

interface ErrorAlertProps extends Omit<AlertProps, 'title' | 'children'> {
  error: unknown;
}

/** Muestra el *problem details* de un `ApiError` (título y detalle), nunca trazas. */
export function ErrorAlert({ error, ...props }: ErrorAlertProps) {
  const { t } = useTranslation();
  const title = error instanceof ApiError ? error.problem.title : t('common.error');
  const detail = error instanceof ApiError ? error.problem.detail : t('common.errorBody');
  return (
    <Alert color="red" role="alert" title={title} {...props}>
      {detail}
    </Alert>
  );
}
