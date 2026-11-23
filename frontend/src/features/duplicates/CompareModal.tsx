import {
  Alert,
  Center,
  Group,
  Loader,
  Modal,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Text,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { useOutputText } from '../documents/useDocuments';
import type { DuplicateGroup } from './useDuplicates';

type Member = DuplicateGroup['members'][number];

/** Las líneas de un texto normalizadas para comparar (sin espacios de más ni mayúsculas); las vacías no cuentan. */
function lineSet(text: string): Set<string> {
  return new Set(
    text
      .split('\n')
      .map((line) => line.trim().replace(/\s+/g, ' ').toLowerCase())
      .filter(Boolean),
  );
}

/**
 * Un lado de la comparación: el Markdown convertido como **texto plano** (React lo escapa: no se interpreta HTML ni
 * Markdown de los documentos). Se resaltan las líneas que no están en el otro lado.
 */
function Side({
  label,
  member,
  text,
  other,
  loading,
  error,
}: {
  label: string;
  member: Member;
  text: string | undefined;
  other: string | undefined;
  loading: boolean;
  error: unknown;
}) {
  const { t } = useTranslation();
  const others = other === undefined ? null : lineSet(other);
  return (
    <Stack gap={4} miw={0}>
      <Text size="sm" fw={500} truncate="end" title={member.key}>
        {label}: {member.key}
      </Text>
      {error ? (
        <ErrorAlert error={error} />
      ) : loading || text === undefined ? (
        <Center h={120}>
          <Loader size="sm" aria-label={t('common.loading')} />
        </Center>
      ) : (
        <ScrollArea h="60vh" type="auto" offsetScrollbars>
          <Text
            component="div"
            size="xs"
            ff="monospace"
            style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
          >
            {text.split('\n').map((line, index) => {
              const normalized = line.trim().replace(/\s+/g, ' ').toLowerCase();
              const only = others !== null && normalized !== '' && !others.has(normalized);
              return (
                <div
                  // Las líneas no cambian mientras el modal está abierto: el índice basta como clave.
                  key={index}
                  style={only ? { background: 'var(--mantine-color-yellow-light)' } : undefined}
                >
                  {line || ' '}
                </div>
              );
            })}
          </Text>
        </ScrollArea>
      )}
    </Stack>
  );
}

/**
 * «Ver diferencias» (2.2): dos documentos de un grupo lado a lado, con el texto de su conversión. Solo los que tienen
 * conversión; se elige cuáles comparar.
 */
export function CompareModal({
  projectId,
  group,
  onClose,
}: {
  projectId: number;
  group: DuplicateGroup;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const converted = group.members.filter((member) => member.output_path);
  const [left, setLeft] = useState(converted[0]?.key ?? null);
  const [right, setRight] = useState(converted[1]?.key ?? null);
  const leftMember = converted.find((member) => member.key === left) ?? null;
  const rightMember = converted.find((member) => member.key === right) ?? null;
  const leftText = useOutputText(projectId, leftMember?.output_path ?? null);
  const rightText = useOutputText(projectId, rightMember?.output_path ?? null);
  const options = converted.map((member) => ({ value: member.key, label: member.key }));

  return (
    <Modal opened onClose={onClose} title={t('duplicates.compare.title')} size="100%">
      {converted.length < 2 ? (
        <Alert color="gray">{t('duplicates.compare.notConverted')}</Alert>
      ) : (
        <Stack>
          <Text size="sm" c="dimmed">
            {t('duplicates.compare.intro')}
          </Text>
          <Group grow>
            <Select
              label={t('duplicates.compare.left')}
              data={options}
              value={left}
              onChange={setLeft}
              allowDeselect={false}
            />
            <Select
              label={t('duplicates.compare.right')}
              data={options}
              value={right}
              onChange={setRight}
              allowDeselect={false}
            />
          </Group>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            {leftMember && (
              <Side
                label={t('duplicates.compare.left')}
                member={leftMember}
                text={leftText.data}
                other={rightText.data}
                loading={leftText.isPending}
                error={leftText.error}
              />
            )}
            {rightMember && (
              <Side
                label={t('duplicates.compare.right')}
                member={rightMember}
                text={rightText.data}
                other={leftText.data}
                loading={rightText.isPending}
                error={rightText.error}
              />
            )}
          </SimpleGrid>
        </Stack>
      )}
    </Modal>
  );
}
