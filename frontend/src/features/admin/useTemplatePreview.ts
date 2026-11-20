import { useMutation } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';

/** Vista previa del prompt de una plantilla (su perfil y su catálogo), sin llamar al modelo (`templates.manage`). */
export function useTemplatePromptPreview() {
  return useMutation({
    mutationFn: async (markdown: string) =>
      unwrap(await api.POST('/api/v1/taxonomy-templates/prompt-preview', { body: { markdown } })),
  });
}
