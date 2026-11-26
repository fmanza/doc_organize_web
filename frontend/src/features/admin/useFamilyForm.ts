import { useState } from 'react';
import { type AiFamily, type AiField, useUpdateAiFamily } from './useAi';

/** Valores del formulario de una familia, lo que cambia respecto a lo guardado, guardar y borrar. */
export function useFamilyForm(family: AiFamily, encryption: boolean) {
  const update = useUpdateAiFamily();
  const initial = (field: AiField) => (field.secret || field.source !== 'db' ? '' : (field.value ?? ''));
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(family.fields.map((field) => [field.name, initial(field)])),
  );
  const changes = Object.fromEntries(
    family.fields
      .filter((field) => (values[field.name] ?? '').trim() !== '' && values[field.name] !== initial(field))
      .map((field) => [field.name, (values[field.name] ?? '').trim()]),
  );
  const blockedBySecret = !encryption && family.fields.some((field) => field.secret && field.name in changes);
  // Se puede probar sin guardar: basta con que cada obligatorio esté escrito o ya tenga valor (guardado o del entorno).
  const testable = family.fields.every(
    (field) => !field.required || field.name in changes || field.source !== 'none',
  );
  const save = () =>
    update.mutate(
      { family: family.key, fields: changes },
      {
        onSuccess: (saved) =>
          setValues(Object.fromEntries(saved.fields.map((field) => [field.name, initial(field)]))),
      },
    );
  const clear = (name: string) =>
    update.mutate(
      { family: family.key, fields: { [name]: null } },
      { onSuccess: () => setValues((current) => ({ ...current, [name]: '' })) },
    );
  const setValue = (name: string, value: string) => setValues((current) => ({ ...current, [name]: value }));
  return { values, setValue, changes, blockedBySecret, testable, save, clear, update };
}

export type FamilyForm = ReturnType<typeof useFamilyForm>;
