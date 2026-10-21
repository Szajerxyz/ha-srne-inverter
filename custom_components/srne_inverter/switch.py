"""Przełączniki (rejestr 0/1 oraz pojedyncze bity maski)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity
from .registers import BIT_SWITCHES, SWITCHES, BitSwitchDef, SwitchDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [SrneSwitch(coordinator, d) for d in SWITCHES]
        + [SrneBitSwitch(coordinator, d) for d in BIT_SWITCHES]
    )


class SrneSwitch(SrneEntity, SwitchEntity):
    def __init__(self, coordinator, d: SwitchDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address)
        self._d = d
        if d.icon:
            self._attr_icon = d.icon

    @property
    def is_on(self) -> bool | None:
        raw = self._raw
        return None if raw is None else raw == self._d.on

    async def async_turn_on(self, **kwargs) -> None:
        self._guard()
        await self.coordinator.async_write(self._address, self._d.on)

    async def async_turn_off(self, **kwargs) -> None:
        self._guard()
        await self.coordinator.async_write(self._address, self._d.off)


class SrneBitSwitch(SrneEntity, SwitchEntity):
    """Jeden bit rejestru-maski. Zapis: świeży odczyt -> zmiana bitu -> zapis."""

    def __init__(self, coordinator, d: BitSwitchDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address)
        self._d = d
        if d.icon:
            self._attr_icon = d.icon

    @property
    def is_on(self) -> bool | None:
        raw = self._raw
        return None if raw is None else bool((raw >> self._d.bit) & 1)

    async def async_turn_on(self, **kwargs) -> None:
        self._guard()
        await self.coordinator.async_write_bit(self._address, self._d.bit, True)

    async def async_turn_off(self, **kwargs) -> None:
        self._guard()
        await self.coordinator.async_write_bit(self._address, self._d.bit, False)
