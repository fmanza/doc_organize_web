"""Sin GitHub Copilot (web 2.1): se borra la configuración guardada de la familia ``github_copilot_usage``.

Todo el uso de IA se consulta en LiteLLM. El usuario y el PAT (cifrado) de GitHub no se deben quedar guardados sin uso,
así que se borran. Bajar de versión **no** los recupera: la familia vuelve a existir en el código de la 2.0, vacía, y
hay que volver a escribirlos (o seguirán valiendo las variables ``DOC_ORGANIZE_GITHUB_*`` si están definidas).

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM ai_settings WHERE family = 'github_copilot_usage'"))


def downgrade() -> None:
    # Nada que rehacer: los valores borrados (un secreto entre ellos) no se guardan en ningún otro sitio.
    pass
