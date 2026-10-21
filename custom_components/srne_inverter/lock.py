"""Blokada ustawień (encja lock): odblokowanie hasłem falownika (wpisywanym przy odblokowaniu), auto-blokada po czasie."""
from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity
from .registers import LOCKS, LockDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneLock(entry.runtime_data, d) for d in LOCKS)


class SrneLock(SrneEntity, LockEntity):
    """locked = zapisy od użytkowników zablokowane; unlocked = dozwolone (do końca czasu)."""

    def __init__(self, coordinator, d: LockDef) -> None:
        super().__init__(coordinator, d.key, d.name, 0)

    @property
    def available(self) -> bool:
        # nie zależy od odczytu rejestrów
        return self.coordinator.last_update_success

    @property
    def code_format(self) -> str | None:
        return r"^\d{1,5}$"  # hasło falownika: do 5 cyfr (0-65535)

    @property
    def is_locked(self) -> bool:
        return not self.coordinator.write_lock.unlocked

    @property
    def extra_state_attributes(self) -> dict:
        lock = self.coordinator.write_lock
        return {"remaining_seconds": lock.remaining}

    async def async_unlock(self, **kwargs) -> None:
        await self.coordinator.async_unlock(kwargs.get("code"))

    async def async_lock(self, **kwargs) -> None:
        self.coordinator.async_lock()
