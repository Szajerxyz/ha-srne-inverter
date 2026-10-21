"""Parametry liczbowe do zapisu."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity, signed16
from .registers import NUMBERS, NumberDef

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneNumber(entry.runtime_data, d) for d in NUMBERS)


class SrneNumber(SrneEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, d: NumberDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address)
        self._d = d
        self._attr_native_min_value = d.minimum
        self._attr_native_max_value = d.maximum
        self._attr_native_step = d.step
        self._attr_native_unit_of_measurement = d.unit
        if d.icon:
            self._attr_icon = d.icon

    @property
    def native_value(self) -> float | None:
        raw = self._raw
        if raw is None:
            return None
        return round(signed16(raw, self._d.signed) * self._d.scale, 3)

    async def async_set_native_value(self, value: float) -> None:
        self._guard()
        raw = int(round(value / self._d.scale))
        limit = (self.coordinator.data or {}).get(self._d.must_be_below) if self._d.must_be_below else None
        if limit is not None and raw > limit - 1:
            raise ServiceValidationError(
                "Ta wartość musi być niższa od maksymalnego napięcia ładowania "
                f"(obecnie {round(limit * self._d.scale, 1)} V) o co najmniej jeden krok"
            )
        if raw < 0:
            raw += 65536  # kod uzupełnień do dwóch (rejestr ze znakiem)
        if not self._d.mirrors and self._d.keep_below is None:
            await self.coordinator.async_write(self._address, raw)
            return
        data = self.coordinator.data or {}
        current = data.get(self._address)
        addrs = (self._address, *self._d.mirrors)
        writes: list[tuple[int, int]] = []
        other = self._d.keep_below
        if other is not None and data.get(other) is not None and data[other] > raw - 1:
            writes.append((other, max(raw - 1, 0)))
        # obniżanie: od ostatniego rejestru grupy; podnoszenie: od pierwszego
        ordered = addrs[::-1] if (current is None or raw < current) else addrs
        writes.extend((a, raw) for a in ordered)
        _LOGGER.debug(
            "%s: nowa wartość %s, obecnie %s, rejestr ograniczany (%s) = %s, kolejka zapisów: %s",
            self._d.key, raw, current,
            hex(other) if other is not None else None,
            data.get(other) if other is not None else None,
            [(hex(a), v) for a, v in writes],
        )
        await self.coordinator.async_write_many(writes)
