import { Anchor, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <Stack>
      <Title order={2}>{t('notFound.title')}</Title>
      <Text>{t('notFound.body')}</Text>
      <Anchor component={Link} to="/">
        {t('notFound.back')}
      </Anchor>
    </Stack>
  );
}
