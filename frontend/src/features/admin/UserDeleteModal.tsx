import {
  Alert,
  Anchor,
  Button,
  Center,
  Group,
  List,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type User, useDeleteUser, useUserDeletionCheck } from './useAdmin';

/**
 * Borrar un usuario (2.7, ADR-016). Primero pide la comprobación: si algo depende de él, explica qué y cómo
 * resolverlo; si no, resume lo que se borra y exige teclear su nombre de usuario (es irreversible).
 */
export function UserDeleteModal({ user, onClose }: { user: User; onClose: () => void }) {
  const { t } = useTranslation();
  const check = useUserDeletionCheck(user.id);
  const remove = useDeleteUser();
  const [typed, setTyped] = useState('');

  return (
    <Modal
      opened
      onClose={onClose}
      title={t('admin.users.delete.title', { username: user.username })}
      size="lg"
    >
      <Stack>
        {check.isPending && (
          <Center>
            <Loader aria-label={t('common.loading')} />
          </Center>
        )}
        {check.isError && <ErrorAlert error={check.error} />}
        {check.data && !check.data.can_delete && (
          <>
            <Alert color="orange" title={t('admin.users.delete.blockedTitle')}>
              <List size="sm">
                {check.data.reasons.map((reason) => (
                  <List.Item key={reason}>
                    {t(`admin.users.delete.reason.${reason}`, { count: check.data.active_runs })}
                  </List.Item>
                ))}
              </List>
            </Alert>
            {check.data.sole_owner_projects.length > 0 && (
              <Stack gap={4}>
                <Text size="sm">{t('admin.users.delete.soleOwnerProjects')}</Text>
                <List size="sm">
                  {check.data.sole_owner_projects.map((project) => (
                    <List.Item key={project.id}>
                      <Anchor component={Link} to={`/projects/${project.id}`}>
                        {project.name}
                      </Anchor>
                    </List.Item>
                  ))}
                </List>
              </Stack>
            )}
            <Group justify="flex-end">
              <Button onClick={onClose}>{t('common.close')}</Button>
            </Group>
          </>
        )}
        {check.data?.can_delete && (
          <>
            <Alert color="red" title={t('admin.users.delete.warningTitle')}>
              {t('admin.users.delete.warning')}
            </Alert>
            <Text size="sm">{t('admin.users.delete.sessions', { count: check.data.sessions })}</Text>
            {check.data.memberships.length > 0 && (
              <Stack gap={4}>
                <Text size="sm">{t('admin.users.delete.memberships')}</Text>
                <List size="sm">
                  {check.data.memberships.map((project) => (
                    <List.Item key={project.id}>
                      {project.name} ({t(`projects.roles.${project.role}`)})
                    </List.Item>
                  ))}
                </List>
              </Stack>
            )}
            <TextInput
              label={t('admin.users.delete.confirm', { username: user.username })}
              value={typed}
              onChange={(event) => setTyped(event.currentTarget.value)}
              autoComplete="off"
            />
            {remove.isError && <ErrorAlert error={remove.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                disabled={typed.trim().toLowerCase() !== user.username}
                loading={remove.isPending}
                onClick={() => remove.mutate(user.id, { onSuccess: onClose })}
              >
                {t('admin.users.delete.submit')}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
}
