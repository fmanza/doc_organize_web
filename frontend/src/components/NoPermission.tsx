import { Alert } from '@mantine/core';
import { useTranslation } from 'react-i18next';

export function NoPermission() {
  const { t } = useTranslation();
  return (
    <Alert color="yellow" role="alert" title={t('common.noPermission')}>
      {t('common.noPermissionBody')}
    </Alert>
  );
}
