import {
  Alert,
  Button,
  Group,
  Input,
  Modal,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { zodResolver } from '../../components/forms';
import {
  type LocationOut,
  type LocationUpdate,
  parsePatterns,
  useCreateLocation,
  useUpdateLocation,
} from './useLocations';

function buildSchema(editing: boolean) {
  return z.object({
    name: z.string().trim().min(1, 'auth.required').max(128),
    // Al crear hay que elegir una subcarpeta de /mnt; al editar no se puede cambiar.
    path: editing ? z.string() : z.string().min(1, 'locations.form.pathRequired'),
    displayPath: z.string().max(1024),
    kind: z.enum(['local', 'network']),
    usage: z.enum(['source', 'destination', 'both']),
    access: z.enum(['ro', 'rw']),
    /** Patrones de nombre que no se escanean, uno por línea (1.4.1; el servidor los valida). */
    patterns: z.string(),
  });
}
type LocationForm = z.infer<ReturnType<typeof buildSchema>>;

interface LocationFormModalProps {
  /** Ubicación a editar; `null` para registrar una nueva. */
  location: LocationOut | null;
  opened: boolean;
  onClose: () => void;
}

/** Alta y edición de ubicaciones (solo admin). Se monta con `key` distinta por ubicación para reiniciar el estado. */
export function LocationFormModal({ location, opened, onClose }: LocationFormModalProps) {
  const { t } = useTranslation();
  const create = useCreateLocation();
  const update = useUpdateLocation();
  const mutation = location ? update : create;
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<LocationForm>({
    resolver: zodResolver(buildSchema(location !== null)),
    defaultValues: {
      name: location?.name ?? '',
      path: '',
      displayPath: location?.display_path ?? '',
      kind: location?.kind ?? 'local',
      usage: location?.usage ?? 'source',
      access: location?.access ?? 'ro',
      patterns: (location?.ignore_patterns ?? []).join('\n'),
    },
  });
  // Los patrones solo valen en ubicaciones de origen: en una de destino ni se muestran ni se envían (se conservan).
  const isSource = useWatch({ control, name: 'usage' }) !== 'destination';

  const onSubmit = handleSubmit((values) => {
    const patterns =
      values.usage === 'destination' ? {} : { ignore_patterns: parsePatterns(values.patterns) };
    if (location) {
      const body: LocationUpdate = {
        name: values.name,
        display_path: values.displayPath,
        kind: values.kind,
        usage: values.usage,
        access: values.access,
        ...patterns,
      };
      update.mutate({ id: location.id, body }, { onSuccess: onClose });
    } else {
      create.mutate(
        {
          name: values.name,
          path: values.path,
          display_path: values.displayPath || null,
          kind: values.kind,
          usage: values.usage,
          access: values.access,
          ...patterns,
        },
        { onSuccess: onClose },
      );
    }
  });

  const segmented = (name: 'kind' | 'usage' | 'access', options: string[]) => (
    <Input.Wrapper label={t(`locations.fields.${name}`)} id={`location-${name}`}>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <SegmentedControl
            fullWidth
            aria-labelledby={`location-${name}-label`}
            data={options.map((value) => ({ value, label: t(`locations.${name}.${value}`) }))}
            value={field.value}
            onChange={field.onChange}
          />
        )}
      />
    </Input.Wrapper>
  );

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="lg"
      title={
        location ? t('locations.form.editTitle', { name: location.name }) : t('locations.form.createTitle')
      }
    >
      <form onSubmit={(event) => void onSubmit(event)} noValidate>
        <Stack>
          {mutation.isError && <ErrorAlert error={mutation.error} />}
          <TextInput
            label={t('locations.fields.name')}
            required
            error={errors.name?.message && t(errors.name.message)}
            data-autofocus
            {...register('name')}
          />
          {location ? (
            <Input.Wrapper
              label={t('locations.fields.containerPath')}
              description={t('locations.form.pathFixed')}
            >
              <Text ff="monospace" size="sm">
                {location.container_path}
              </Text>
            </Input.Wrapper>
          ) : (
            <Controller
              control={control}
              name="path"
              render={({ field }) => (
                <Input.Wrapper
                  label={t('locations.fields.folder')}
                  description={t('locations.form.folderHint')}
                  error={errors.path?.message && t(errors.path.message)}
                  required
                >
                  <FolderBrowser
                    locationId={null}
                    rootLabel="/mnt"
                    selected={field.value}
                    onSelect={(path) => field.onChange(path)}
                  />
                </Input.Wrapper>
              )}
            />
          )}
          <TextInput
            label={t('locations.fields.displayPath')}
            description={t('locations.form.displayPathHint')}
            {...register('displayPath')}
          />
          {segmented('usage', ['source', 'destination', 'both'])}
          {segmented('access', ['ro', 'rw'])}
          {segmented('kind', ['local', 'network'])}
          {isSource && (
            <Stack gap="xs">
              <Textarea
                label={t('locations.patterns.label')}
                description={`${t('locations.patterns.intro')} ${t('locations.patterns.examples')}`}
                rows={4}
                styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
                {...register('patterns')}
              />
              <Alert color="yellow">{t('locations.patterns.warning')}</Alert>
            </Stack>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {location ? t('common.save') : t('locations.form.create')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
