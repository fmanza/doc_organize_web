import { Card, Center, Loader, SegmentedControl, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { canDo, useProject } from '../projects/useProjects';
import { CompareCard } from './CompareCard';
import { ContextNav } from './ContextNav';
import { EvaluationCard } from './EvaluationCard';
import { GoldCard } from './GoldCard';
import { AuditCard } from './QualityAuditCard';
import { type GoldSource } from './qualityReport';
import { useQuality } from './useQuality';

/**
 * Calidad de la clasificación (W5, doc_organize 2.0 G3): métricas por eje contra una referencia (Excel subido o
 * decisiones del proyecto) y «Comparar cambios» con una clasificación de prueba que no guarda nada.
 */
export function QualityPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const quality = useQuality(projectId);
  const [source, setSource] = useState<GoldSource>('xlsx');

  if (project.isError || quality.isError) {
    return <ErrorAlert error={project.error ?? quality.error} />;
  }
  if (!project.data || !quality.data) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  const editable = canDo(project.data, 'editor');
  const data = quality.data;
  const ready = source === 'decisions' ? data.decisions_available : Boolean(data.gold);

  return (
    <Stack>
      <ContextNav projectId={projectId} active="calidad" />
      <Title order={3}>{t('quality.title')}</Title>
      <Text c="dimmed">{t('quality.intro')}</Text>
      <GoldCard projectId={projectId} quality={data} editable={editable} />
      <Card withBorder>
        <SegmentedControl
          value={source}
          onChange={(value) => setSource(value as GoldSource)}
          aria-label={t('quality.source')}
          data={[
            { value: 'xlsx', label: t('quality.sources.xlsx') },
            { value: 'decisions', label: t('quality.sources.decisions') },
          ]}
        />
        {!ready && (
          <Text size="sm" c="dimmed" mt="xs">
            {t(source === 'decisions' ? 'quality.noDecisions' : 'quality.noGold')}
          </Text>
        )}
      </Card>
      <EvaluationCard projectId={projectId} quality={data} source={source} ready={ready && editable} />
      <CompareCard projectId={projectId} quality={data} source={source} ready={ready && editable} />
      <AuditCard projectId={projectId} quality={data} />
    </Stack>
  );
}
