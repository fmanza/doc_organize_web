"""Ajustes de la instancia."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SettingOut(BaseModel):
    """Ajuste administrable con su valor efectivo, el que tendría sin cambio en la web y su origen."""

    key: str
    value: int
    default: int
    source: Literal["db", "env", "default"]
    group: Literal["security", "locations", "storage", "ai"] = Field(
        description="Sección de la administración: «Ajustes» (security, locations, storage) o «IA › Parámetros» (ai)."
    )


class SettingsPage(BaseModel):
    """Ajustes administrables."""

    items: list[SettingOut]


class SettingsUpdate(BaseModel):
    """Cambios de ajustes: ``clave → valor``; ``null`` vuelve al valor de la variable ``DOW_*`` o por defecto."""

    values: dict[str, int | None]
