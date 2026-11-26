import { Button, Card, FileInput, Group, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { GOLD_DEFAULTS, type Quality, useUploadGold } from './useQuality';

export function GoldCard({
  projectId,
  quality,
  editable,
}: {
  projectId: number;
  quality: Quality;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [sheet, setSheet] = useState<string>(GOLD_DEFAULTS.sheet);
  const [documentColumn, setDocumentColumn] = useState<string>(GOLD_DEFAULTS.documentColumn);
  const [columns, setColumns] = useState<string>(GOLD_DEFAULTS.columns);
  const upload = useUploadGold(projectId);
  const gold = quality.gold;
  return (
    <Card withBorder component="section" aria-label={t('quality.goldTitle')}>
      <Title order={3} size="h4" mb="xs">
        {t('quality.goldTitle')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('quality.goldIntro')}
      </Text>
      {gold ? (
        <Text size="sm" mb="xs">
          {t('quality.goldInfo', {
            file: gold.filename,
            labels: gold.labels,
            axes: gold.axes.join(', '),
            date: formatDateTime(gold.uploaded_at),
            author: gold.uploaded_by ?? '—',
          })}
        </Text>
      ) : (
        <Text size="sm" c="dimmed" mb="xs">
          {t('quality.noGold')}
        </Text>
      )}
      {editable && (
        <Stack gap="xs">
          <FileInput label={t('quality.file')} accept=".xlsx" value={file} onChange={setFile} clearable />
          <Group grow>
            <TextInput
              label={t('quality.sheet')}
              value={sheet}
              onChange={(e) => setSheet(e.currentTarget.value)}
            />
            <TextInput
              label={t('quality.documentColumn')}
              value={documentColumn}
              onChange={(e) => setDocumentColumn(e.currentTarget.value)}
            />
          </Group>
          <TextInput
            label={t('quality.columns')}
            description={t('quality.columnsHelp')}
            value={columns}
            onChange={(e) => setColumns(e.currentTarget.value)}
          />
          {upload.isError && <ErrorAlert error={upload.error} />}
          <Group justify="flex-end">
            <Button
              disabled={!file}
              loading={upload.isPending}
              onClick={() =>
                file &&
                upload.mutate({
                  file,
                  sheet,
                  documentColumn,
                  columns: columns
                    .split(',')
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
            >
              {t('quality.upload')}
            </Button>
          </Group>
        </Stack>
      )}
    </Card>
  );
}
