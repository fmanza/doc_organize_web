import {
  Button,
  CloseButton,
  Group,
  Input,
  Modal,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { zodResolver } from '../../components/forms';
import { useLocations } from '../locations/useLocations';
import { useCreateProject } from './useProjects';

const MAX_SOURCES = 20;

const schema = z
  .object({
    name: z.string().trim().min(1, 'auth.required').max(128),
    description: z.string().max(1024),
    sourceLocationId: z.string().min(1, 'auth.required'),
    sourceSubpaths: z.array(z.string()).min(1, 'projects.form.sourceRequired').max(MAX_SOURCES),
    destinationLocationId: z.string().min(1, 'auth.required'),
    destinationParent: z.string(),
    mode: z.enum(['new', 'existing']),
    newFolder: z.string().trim().max(120),
  })
  .refine((v) => v.mode === 'existing' || v.newFolder.length > 0, {
    path: ['newFolder'],
    message: 'projects.form.folderRequired',
  })
  .refine((v) => v.mode === 'new' || v.destinationParent.length > 0, {
    path: ['destinationParent'],
    message: 'projects.form.existingRequired',
  });
type ProjectForm = z.infer<typeof schema>;

interface ProjectFormModalProps {
  opened: boolean;
  onClose: () => void;
}

/**
 * Alta de proyecto: origen (ubicación de origen + una o varias carpetas) y destino (ubicación `rw` + carpeta nueva o
 * vacía, que pasa a pertenecer al proyecto). El creador queda como propietario.
 */
export function ProjectFormModal({ opened, onClose }: ProjectFormModalProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const create = useCreateProject();
  const { data: locations } = useLocations();
  const {
    register,
    control,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ProjectForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      description: '',
      sourceLocationId: '',
      sourceSubpaths: [],
      destinationLocationId: '',
      destinationParent: '',
      mode: 'new',
      newFolder: '',
    },
  });
  const [sourceId, destinationId, mode, sources] = useWatch({
    control,
    name: ['sourceLocationId', 'destinationLocationId', 'mode', 'sourceSubpaths'],
  });

  const sourceOptions = (locations?.items ?? [])
    .filter((l) => l.usage !== 'destination')
    .map((l) => ({ value: String(l.id), label: l.name }));
  const destinationOptions = (locations?.items ?? [])
    .filter((l) => l.usage !== 'source' && l.access === 'rw')
    .map((l) => ({ value: String(l.id), label: l.name }));
  const sourceName = sourceOptions.find((o) => o.value === sourceId)?.label ?? '';
  const destinationName = destinationOptions.find((o) => o.value === destinationId)?.label ?? '';

  const onSubmit = handleSubmit((values) => {
    create.mutate(
      {
        name: values.name,
        description: values.description || null,
        source_location_id: Number(values.sourceLocationId),
        source_subpaths: values.sourceSubpaths,
        destination_location_id: Number(values.destinationLocationId),
        destination_parent: values.destinationParent,
        new_folder: values.mode === 'new' ? values.newFolder : null,
      },
      {
        onSuccess: (project) => {
          onClose();
          void navigate(`/projects/${project.id}`);
        },
      },
    );
  });

  return (
    <Modal opened={opened} onClose={onClose} size="xl" title={t('projects.form.createTitle')}>
      <form onSubmit={(event) => void onSubmit(event)} noValidate>
        <Stack>
          {create.isError && <ErrorAlert error={create.error} />}
          <TextInput
            label={t('projects.fields.name')}
            required
            data-autofocus
            error={errors.name?.message && t(errors.name.message)}
            {...register('name')}
          />
          <Textarea label={t('projects.fields.description')} rows={3} {...register('description')} />

          <Controller
            control={control}
            name="sourceLocationId"
            render={({ field }) => (
              <Select
                label={t('projects.fields.sourceLocation')}
                description={t('projects.form.sourceHint')}
                required
                data={sourceOptions}
                value={field.value || null}
                onChange={(value) => {
                  field.onChange(value ?? '');
                  setValue('sourceSubpaths', []);
                }}
                error={errors.sourceLocationId?.message && t(errors.sourceLocationId.message)}
                nothingFoundMessage={t('projects.form.noLocations')}
              />
            )}
          />
          {sourceId && (
            <Input.Wrapper
              label={t('projects.fields.sourceSubpaths')}
              error={errors.sourceSubpaths?.message && t(errors.sourceSubpaths.message)}
              required
            >
              <Stack gap="xs">
                <Group gap="xs">
                  {sources.length === 0 && (
                    <Text size="sm" c="dimmed">
                      {t('projects.form.noSources')}
                    </Text>
                  )}
                  {sources.map((path) => (
                    <Group key={path} gap={4} wrap="nowrap">
                      <Text size="sm" ff="monospace">
                        {path || t('projects.form.wholeLocation')}
                      </Text>
                      <CloseButton
                        size="sm"
                        aria-label={t('projects.form.removeSource', { path: path || sourceName })}
                        onClick={() =>
                          setValue(
                            'sourceSubpaths',
                            sources.filter((p) => p !== path),
                          )
                        }
                      />
                    </Group>
                  ))}
                </Group>
                <FolderBrowser
                  key={sourceId}
                  locationId={Number(sourceId)}
                  rootLabel={sourceName}
                  onSelect={(path) => {
                    if (!sources.includes(path) && sources.length < MAX_SOURCES) {
                      setValue('sourceSubpaths', [...sources, path], { shouldValidate: true });
                    }
                  }}
                />
              </Stack>
            </Input.Wrapper>
          )}

          <Controller
            control={control}
            name="destinationLocationId"
            render={({ field }) => (
              <Select
                label={t('projects.fields.destinationLocation')}
                description={t('projects.form.destinationHint')}
                required
                data={destinationOptions}
                value={field.value || null}
                onChange={(value) => {
                  field.onChange(value ?? '');
                  setValue('destinationParent', '');
                }}
                error={errors.destinationLocationId?.message && t(errors.destinationLocationId.message)}
                nothingFoundMessage={t('projects.form.noLocations')}
              />
            )}
          />
          {destinationId && (
            <>
              <Controller
                control={control}
                name="mode"
                render={({ field }) => (
                  <SegmentedControl
                    aria-label={t('projects.form.folderMode')}
                    data={[
                      { value: 'new', label: t('projects.form.modeNew') },
                      { value: 'existing', label: t('projects.form.modeExisting') },
                    ]}
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
              <Controller
                control={control}
                name="destinationParent"
                render={({ field }) => (
                  <Input.Wrapper
                    label={t(mode === 'new' ? 'projects.form.parentFolder' : 'projects.form.emptyFolder')}
                    description={t(mode === 'new' ? 'projects.form.parentHint' : 'projects.form.emptyHint')}
                    error={errors.destinationParent?.message && t(errors.destinationParent.message)}
                  >
                    <FolderBrowser
                      key={destinationId}
                      locationId={Number(destinationId)}
                      rootLabel={destinationName}
                      selected={field.value}
                      onSelect={(path) => field.onChange(path)}
                    />
                  </Input.Wrapper>
                )}
              />
              {mode === 'new' && (
                <TextInput
                  label={t('projects.form.newFolder')}
                  description={t('projects.form.newFolderHint')}
                  required
                  error={errors.newFolder?.message && t(errors.newFolder.message)}
                  {...register('newFolder')}
                />
              )}
            </>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={create.isPending}>
              {t('projects.form.create')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
