import { Button, Card, Group, Radio, Select, SimpleGrid, Stack, TagsInput, Text, Title } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { ProfileCard } from './ProfileCard';
import { type Catalog, type NotReady, type Selection, stepHref, useTemplates } from './useContext';

/** Catálogos agrupados: sin taxonomía (carpetas o lista de dominios) y con taxonomía (plantilla o manifiesto). */
const GROUPS: readonly { key: 'none' | 'taxonomy'; catalogs: readonly Catalog[] }[] = [
  { key: 'none', catalogs: ['discover', 'domains'] },
  { key: 'taxonomy', catalogs: ['template', 'manifest'] },
];

/**
 * Paso 1 · Taxonomía (2026-11-22): cómo se clasifican los documentos, antes de construir. Elige el catálogo y, según
 * él, la lista de dominios, la plantilla (con «Personalizar para este proyecto») o el manifiesto; después, el perfil
 * del proyecto según `profileMode`. Sin permiso de construir, todo se ve en solo lectura.
 */
export function TaxonomyStep({
  projectId,
  editable,
  selection,
  onSelectionChange,
  domains,
  onDomainsChange,
  onUseTemplate,
  copyError,
  manifest,
  notReady,
  onProfileDirty,
  onCopyProfile,
}: {
  projectId: number;
  editable: boolean;
  selection: Selection;
  onSelectionChange: (selection: Selection) => void;
  domains: string[];
  onDomainsChange: (domains: string[]) => void;
  onUseTemplate: (name: string) => void;
  copyError: unknown;
  /** Bloque del manifiesto: con su catálogo; en solo lectura, siempre (la página decide si va plegado). */
  manifest: ReactNode;
  notReady: NotReady | null;
  onProfileDirty: (dirty: boolean) => void;
  onCopyProfile: ((markdown: string) => void) | undefined;
}) {
  const { t } = useTranslation();
  const templates = useTemplates();
  const { catalog, template } = selection;

  return (
    <Stack>
      <Card withBorder component="section" aria-label={t('context.taxonomy.title')}>
        <Title order={3} size="h4" mb="xs">
          {t('context.taxonomy.title')}
        </Title>
        <Radio.Group
          value={catalog}
          onChange={(value) => onSelectionChange({ catalog: value as Catalog, template })}
          aria-label={t('context.build.catalog')}
        >
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            {GROUPS.map((group) => (
              <Stack key={group.key} gap="xs">
                <Text size="sm" fw={500}>
                  {t(`context.taxonomy.groups.${group.key}`)}
                </Text>
                {group.catalogs.map((value) => (
                  <Radio
                    key={value}
                    value={value}
                    label={t(`context.catalog.${value}`)}
                    description={t(`context.build.help.${value}`)}
                    disabled={!editable}
                  />
                ))}
              </Stack>
            ))}
          </SimpleGrid>
        </Radio.Group>

        {catalog === 'domains' && (
          <TagsInput
            mt="md"
            label={t('context.build.domains')}
            description={t('context.build.domainsHelp')}
            value={domains}
            onChange={onDomainsChange}
            maxTags={100}
            clearable
            readOnly={!editable}
          />
        )}
        {catalog === 'template' && (
          <Select
            mt="md"
            label={t('context.build.template')}
            data={(templates.data ?? []).map((item) => ({
              value: item.name,
              label: item.title ? `${item.title} (${item.name})` : item.name,
            }))}
            value={template}
            onChange={(value) => onSelectionChange({ catalog, template: value })}
            searchable
            readOnly={!editable}
            nothingFoundMessage={t('context.build.noTemplates')}
          />
        )}
        {editable && catalog === 'template' && template !== null && (
          <Group gap="xs" mt="xs">
            <Button variant="default" size="xs" onClick={() => onUseTemplate(template)}>
              {t('context.build.useTemplateAsManifest')}
            </Button>
            <Text size="xs" c="dimmed">
              {t('context.build.useTemplateAsManifestHint')}
            </Text>
          </Group>
        )}
        {copyError !== null && <ErrorAlert error={copyError} mt="xs" />}
        {templates.isError && catalog === 'template' && <ErrorAlert error={templates.error} mt="xs" />}
      </Card>

      {(catalog === 'manifest' || !editable) && manifest}

      <ProfileCard
        projectId={projectId}
        editable={editable}
        selection={selection}
        onDirtyChange={onProfileDirty}
        onCopyToManifest={onCopyProfile}
      />

      {editable && (
        <Group justify="flex-end" align="center">
          {notReady && (
            <Text size="sm" c="dimmed" role="status">
              {t(`context.build.notReady.${notReady}`)}
            </Text>
          )}
          {notReady ? (
            <Button disabled>{t('context.taxonomy.next')}</Button>
          ) : (
            <Button component={Link} to={stepHref(projectId, 'construir')}>
              {t('context.taxonomy.next')}
            </Button>
          )}
        </Group>
      )}
    </Stack>
  );
}
