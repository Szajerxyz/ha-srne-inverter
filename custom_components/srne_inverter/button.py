"""Przyciski (np. restart falownika)."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity
from .registers import BUTTONS, ButtonDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneButton(entry.runtime_data, d) for d in BUTTONS)


class SrneButton(SrneEntity, ButtonEntity):
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator, d: ButtonDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address)
        self._d = d
        if d.icon:
            self._attr_icon = d.icon

    @property
    def available(self) -> bool:
        # rejestr jest tylko do zapisu - nie sprawdzamy jego odczytu
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        self._guard()
        await self.coordinator.async_write(self._address, self._d.value)
