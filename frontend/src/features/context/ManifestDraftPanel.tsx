import { Alert, Anchor, Button, Card, Group, NumberInput, Text } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useAiStatus } from '../admin/useAi';
import { useTaxonomyDraft } from './useContext';

/**
 * Borrador del manifiesto con IA: lanza el run `taxonomy_draft`, espera a que termine y entrega el Markdown a
 * `onDraft` **sin guardarlo** (la página pide confirmación si sustituye otro texto).
 */
export function DraftPanel({
  projectId,
  onDraft,
}: {
  projectId: number;
  onDraft: (markdown: string) => void;
}) {
  const { t } = useTranslation();
  const status = useAiStatus();
  const [sampleSize, setSampleSize] = useState(25);
  const draft = useTaxonomyDraft(projectId, onDraft);
  const available = status.data?.taxonomy_design === true;

  return (
    <Card withBorder mb="sm" component="section" aria-label={t('context.ai.draftTitle')}>
      <Text fw={500} size="sm">
        {t('context.ai.draftTitle')}
      </Text>
      <Text size="xs" c="dimmed" mb="xs">
        {t(available ? 'context.ai.draftHelp' : 'context.ai.notConfigured.taxonomy_design')}
      </Text>
      <Group align="flex-end">
        <NumberInput
          label={t('context.ai.sampleSize')}
          min={1}
          max={60}
          allowDecimal={false}
          clampBehavior="strict"
          value={sampleSize}
          onChange={(value) => setSampleSize(typeof value === 'number' ? value : 25)}
          w={180}
          disabled={!available}
        />
        <Button
          variant="light"
          color="grape"
          onClick={() => draft.start(sampleSize)}
          loading={draft.running}
          disabled={!available}
        >
          {t('context.ai.draft')}
        </Button>
        {draft.runId && (
          <Anchor component={Link} to={`/runs/${draft.runId}`} size="sm">
            {t('context.ai.openRun')}
          </Anchor>
        )}
      </Group>
      {draft.error && <ErrorAlert error={draft.error} mt="xs" />}
      {draft.failure && (
        <Alert color="red" role="alert" mt="xs">
          {draft.failure}
        </Alert>
      )}
      {draft.loaded && (
        <Alert color="grape" role="status" mt="xs" title={t('context.ai.draftLoaded')}>
          {draft.loaded.reasoning ?? t('context.ai.draftLoadedBody')}
          <Text size="xs" mt={4}>
            {t('context.ai.draftSample', {
              sample: draft.loaded.sample_documents,
              total: draft.loaded.total_documents,
            })}
          </Text>
        </Alert>
      )}
    </Card>
  );
}
