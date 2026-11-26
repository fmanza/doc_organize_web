import {
  Anchor,
  Badge,
  Button,
  Group,
  Modal,
  MultiSelect,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { AxisBadges } from './Axes';
import { type ContextOut } from './useContext';
import { type DecisionIn, type ReviewItem, useDecide } from './useReview';

export function ReviewRow({
  item,
  context,
  projectId,
  editable,
}: {
  item: ReviewItem;
  context: ContextOut;
  projectId: number;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const decide = useDecide(projectId);
  const [changing, setChanging] = useState(false);
  const doc = item.document;
  const axes = context.taxonomy_axes ?? [];
  const axisName = axes.find((axis) => axis.key === item.axis)?.name ?? item.axis;
  const confirmAxes = Object.fromEntries(
    Object.entries(doc?.axes ?? {})
      .filter(([, values]) => values.length > 0)
      .map(([key, values]) => [key, values.map((value) => value.slug)]),
  );
  const send = (body: Omit<DecisionIn, 'document_key'>) =>
    decide.mutate({ document_key: item.document_key, ...body });

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm">{doc?.title ?? item.document_key}</Text>
        <Text size="xs" ff="monospace" c="dimmed" style={{ wordBreak: 'break-all' }}>
          {item.document_key}
        </Text>
        {doc && <AxisBadges axes={axes} values={doc.axes} />}
        {doc?.version && (
          <Text size="xs" c="dimmed">
            {t('review.version', { version: doc.version })}
            {doc.is_current && ` · ${t('review.current')}`}
          </Text>
        )}
        {doc?.output_path && (
          <Anchor
            component={Link}
            to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(doc.output_path)}`}
            size="xs"
          >
            {t('context.documents.view')}
          </Anchor>
        )}
      </Table.Td>
      <Table.Td>
        <Badge variant="light" color={item.priority <= 1 ? 'red' : item.priority <= 3 ? 'orange' : 'gray'}>
          {t(`review.reasons.${item.reason}`)}
        </Badge>
        {item.axis && (
          <Text size="xs" mt={2}>
            {axisName}
            {item.value && `: ${item.value}`}
            {typeof item.confidence === 'number' && ` (${Math.round(item.confidence * 100)} %)`}
          </Text>
        )}
        {item.detail && (
          <Text size="xs" c="dimmed">
            {item.detail}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        {item.decision ? (
          <Text size="xs">
            {t('review.decided', {
              action: t(`review.actions.${item.decision.action}`),
              author: item.decision.author ?? '—',
              date: formatDateTime(item.decision.decided_at),
            })}
          </Text>
        ) : (
          <Text size="xs" c="dimmed">
            {t('review.noDecision')}
          </Text>
        )}
        {editable && doc && (
          <Group gap={4} mt={4}>
            <Button
              size="compact-xs"
              variant="light"
              disabled={Object.keys(confirmAxes).length === 0}
              loading={decide.isPending && decide.variables?.action === 'confirm'}
              onClick={() => send({ action: 'confirm', axes: confirmAxes })}
            >
              {t('review.actions.confirm')}
            </Button>
            <Button size="compact-xs" variant="light" onClick={() => setChanging(true)}>
              {t('review.change')}
            </Button>
            <Button
              size="compact-xs"
              variant="light"
              color="red"
              loading={decide.isPending && decide.variables?.action === 'exclude'}
              onClick={() => send({ action: 'exclude' })}
            >
              {t('review.actions.exclude')}
            </Button>
            {doc.version_group && !doc.is_current && (
              <Button
                size="compact-xs"
                variant="light"
                loading={decide.isPending && decide.variables?.action === 'set_current_version'}
                onClick={() => send({ action: 'set_current_version' })}
              >
                {t('review.actions.set_current_version')}
              </Button>
            )}
          </Group>
        )}
        {decide.isError && <ErrorAlert error={decide.error} mt={4} />}
        {changing && (
          <ChangeAxisModal
            item={item}
            context={context}
            onClose={() => setChanging(false)}
            onSave={(axis, values, reason) =>
              decide.mutate(
                { document_key: item.document_key, action: 'set_axis', axes: { [axis]: values }, reason },
                { onSuccess: () => setChanging(false) },
              )
            }
            saving={decide.isPending}
          />
        )}
      </Table.Td>
    </Table.Tr>
  );
}

/** Fijar los valores de un eje (solo valores del catálogo; uno en los ejes que organizan carpetas). */
function ChangeAxisModal({
  item,
  context,
  onClose,
  onSave,
  saving,
}: {
  item: ReviewItem;
  context: ContextOut;
  onClose: () => void;
  onSave: (axis: string, values: string[], reason: string | null) => void;
  saving: boolean;
}) {
  const { t } = useTranslation();
  const axes = context.taxonomy_axes ?? [];
  const [axisKey, setAxisKey] = useState<string | null>(item.axis ?? axes[0]?.key ?? null);
  const axis = axes.find((candidate) => candidate.key === axisKey);
  const current = (axisKey && item.document?.axes[axisKey]?.map((value) => value.slug)) || [];
  const [values, setValues] = useState<string[]>(current);
  const [reason, setReason] = useState('');
  const single = !axis?.multiple || Boolean(axis?.organizes);
  const options = (axis?.values ?? []).map((value) => ({ value: value.slug, label: value.name }));
  return (
    <Modal opened onClose={onClose} title={t('review.changeTitle')}>
      <Stack>
        <Select
          label={t('review.axis')}
          value={axisKey}
          data={axes.map((candidate) => ({ value: candidate.key, label: candidate.name }))}
          onChange={(value) => {
            setAxisKey(value);
            setValues((value && item.document?.axes[value]?.map((v) => v.slug)) || []);
          }}
        />
        {single ? (
          <Select
            label={t('review.value')}
            value={values[0] ?? null}
            data={options}
            searchable
            clearable={!axis?.organizes}
            onChange={(value) => setValues(value ? [value] : [])}
          />
        ) : (
          <MultiSelect
            label={t('review.values')}
            value={values}
            data={options}
            searchable
            onChange={setValues}
          />
        )}
        <TextInput
          label={t('review.why')}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={!axisKey || (Boolean(axis?.organizes) && values.length !== 1)}
            onClick={() => axisKey && onSave(axisKey, values, reason.trim() || null)}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
