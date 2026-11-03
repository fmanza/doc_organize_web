import {
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount } from '../../components/format';
import { useMe } from '../auth/useAuth';
import {
  type Tenant,
  useCreateTenant,
  useDeleteTenant,
  useRenameTenant,
  useSwitchTenant,
  useTenants,
} from './useTenancy';

const SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/;

/** Tenants de la instancia (sustituye a `admin_tenants.html.j2`); solo el admin de instancia. */
export function TenantsPage() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const tenants = useTenants();
  const create = useCreateTenant();
  const switchTenant = useSwitchTenant();
  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');
  const [renaming, setRenaming] = useState<Tenant | null>(null);
  const [deleting, setDeleting] = useState<Tenant | null>(null);
  const slugValid = SLUG.test(slug);

  return (
    <Stack>
      <Title order={2}>{t('tenants.title')}</Title>
      <Text c="dimmed">{t('tenants.intro')}</Text>
      <Card withBorder component="section" aria-label={t('tenants.new')}>
        <Title order={3} size="h4" mb="xs">
          {t('tenants.new')}
        </Title>
        <Group align="flex-end">
          <TextInput
            label={t('tenants.slug')}
            description={t('tenants.slugHint')}
            value={slug}
            onChange={(event) => setSlug(event.currentTarget.value.trim().toLowerCase())}
            error={slug && !slugValid ? t('tenants.slugInvalid') : undefined}
            maxLength={63}
          />
          <TextInput
            label={t('tenants.name')}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={128}
          />
          <Button
            onClick={() =>
              create.mutate(
                { slug, name: name.trim() },
                {
                  onSuccess: () => {
                    setSlug('');
                    setName('');
                  },
                },
              )
            }
            disabled={!slugValid || !name.trim()}
            loading={create.isPending}
          >
            {t('tenants.create')}
          </Button>
        </Group>
        {create.isError && <ErrorAlert error={create.error} mt="xs" />}
      </Card>
      {switchTenant.isError && <ErrorAlert error={switchTenant.error} />}
      {tenants.isPending ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : tenants.isError ? (
        <ErrorAlert error={tenants.error} />
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('tenants.name')}</Table.Th>
                <Table.Th>{t('tenants.slug')}</Table.Th>
                <Table.Th>{t('tenants.users')}</Table.Th>
                <Table.Th>{t('tenants.projects')}</Table.Th>
                <Table.Th>{t('tenants.locations')}</Table.Th>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tenants.data.items.map((tenant) => {
                const acting = me?.acting_tenant.id === tenant.id;
                return (
                  <Table.Tr key={tenant.id}>
                    <Table.Td>
                      {tenant.name}
                      {acting && (
                        <Text size="xs" c="teal">
                          {t('tenants.acting')}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td ff="monospace">{tenant.slug}</Table.Td>
                    <Table.Td>{formatCount(tenant.users)}</Table.Td>
                    <Table.Td>{formatCount(tenant.projects)}</Table.Td>
                    <Table.Td>{formatCount(tenant.locations)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <Button
                          size="xs"
                          variant="light"
                          disabled={acting}
                          loading={switchTenant.isPending && switchTenant.variables === tenant.id}
                          onClick={() => switchTenant.mutate(tenant.id)}
                          aria-label={t('tenants.actInLabel', { name: tenant.name })}
                        >
                          {t('tenants.actIn')}
                        </Button>
                        <Button
                          size="xs"
                          variant="default"
                          onClick={() => setRenaming(tenant)}
                          aria-label={t('tenants.renameLabel', { name: tenant.name })}
                        >
                          {t('tenants.rename')}
                        </Button>
                        <Tooltip label={t('tenants.notEmpty')} disabled={tenant.empty}>
                          <Button
                            size="xs"
                            color="red"
                            variant="light"
                            disabled={!tenant.empty || tenant.slug === 'default'}
                            onClick={() => setDeleting(tenant)}
                            aria-label={t('tenants.deleteLabel', { name: tenant.name })}
                          >
                            {t('common.delete')}
                          </Button>
                        </Tooltip>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {renaming && <RenameModal tenant={renaming} onClose={() => setRenaming(null)} />}
      {deleting && <DeleteModal tenant={deleting} onClose={() => setDeleting(null)} />}
    </Stack>
  );
}

function RenameModal({ tenant, onClose }: { tenant: Tenant; onClose: () => void }) {
  const { t } = useTranslation();
  const rename = useRenameTenant();
  const [name, setName] = useState(tenant.name);
  return (
    <Modal opened onClose={onClose} title={t('tenants.renameLabel', { name: tenant.name })}>
      <Stack>
        {rename.isError && <ErrorAlert error={rename.error} />}
        <TextInput
          label={t('tenants.name')}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          maxLength={128}
          data-autofocus
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={() => rename.mutate({ id: tenant.id, name: name.trim() }, { onSuccess: onClose })}
            disabled={!name.trim()}
            loading={rename.isPending}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function DeleteModal({ tenant, onClose }: { tenant: Tenant; onClose: () => void }) {
  const { t } = useTranslation();
  const remove = useDeleteTenant();
  return (
    <Modal opened onClose={onClose} title={t('tenants.deleteLabel', { name: tenant.name })}>
      <Stack>
        <Text>{t('tenants.deleteBody', { name: tenant.name })}</Text>
        {remove.isError && <ErrorAlert error={remove.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            onClick={() => remove.mutate(tenant.id, { onSuccess: onClose })}
            loading={remove.isPending}
          >
            {t('common.delete')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
