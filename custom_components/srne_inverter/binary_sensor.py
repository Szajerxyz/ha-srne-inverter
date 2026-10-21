"""Sensory binarne (błędy, alarmy BMS)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity
from .registers import BINARY_SENSORS, BinarySensorDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneBinarySensor(entry.runtime_data, d) for d in BINARY_SENSORS)


class SrneBinarySensor(SrneEntity, BinarySensorEntity):
    def __init__(self, coordinator, d: BinarySensorDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address, d.words)
        self._attr_device_class = (
            BinarySensorDeviceClass(d.device_class) if d.device_class else None
        )

    @property
    def is_on(self) -> bool | None:
        raw = self._raw
        return None if raw is None else raw != 0
