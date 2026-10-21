"""Godziny start/stop ładowania z sieci (starszy bajt = godz., młodszy = min)."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity
from .registers import TIMES, TimeDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneTime(entry.runtime_data, d) for d in TIMES)


class SrneTime(SrneEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, d: TimeDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address)

    @property
    def native_value(self) -> time | None:
        raw = self._raw
        if raw is None:
            return None
        hour, minute = raw >> 8, raw & 0xFF
        if hour > 23 or minute > 59:
            return None
        return time(hour, minute)

    async def async_set_value(self, value: time) -> None:
        self._guard()
        await self.coordinator.async_write(self._address, (value.hour << 8) | value.minute)
