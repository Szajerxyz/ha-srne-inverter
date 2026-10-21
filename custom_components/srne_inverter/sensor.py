"""Sensory (odczyty)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SrneConfigEntry
from .entity import SrneEntity, signed16
from .faults import FAULTS
from .registers import SENSORS, SensorDef


async def async_setup_entry(
    hass: HomeAssistant, entry: SrneConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(SrneSensor(entry.runtime_data, d) for d in SENSORS)


class SrneSensor(SrneEntity, SensorEntity):
    def __init__(self, coordinator, d: SensorDef) -> None:
        super().__init__(coordinator, d.key, d.name, d.address, d.words)
        self._d = d
        self._attr_native_unit_of_measurement = d.unit
        self._names = coordinator.names
        if d.options and d.strict:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = [self._names.option(d.key, o) for o in d.options.values()]
        else:
            self._attr_device_class = SensorDeviceClass(d.device_class) if d.device_class else None
        self._attr_state_class = SensorStateClass(d.state_class) if d.state_class else None
        self._attr_suggested_display_precision = d.precision
        if d.icon:
            self._attr_icon = d.icon
        self._attr_entity_registry_enabled_default = d.enabled_default
        if d.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _active_faults(self) -> list[int]:
        raw = self._raw or 0
        return [c for i in range(self._d.words) if (c := (raw >> (16 * i)) & 0xFFFF)]

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._d.kind == "fault_text":
            details = []
            for code in self._active_faults():
                info = self._names.fault(code)
                camel, affects = FAULTS.get(code, (None, None))
                details.append(
                    {
                        "code": code,
                        "name": camel,
                        "affects_output": affects,
                        "title": info["title"],
                        "description": info["description"],
                        "remedy": info["remedy"],
                    }
                )
            return {"faults": details}
        if self._d.key != "battery_power":
            return None
        value = self.native_value
        if value is None:
            return None
        direction = "charging" if value < 0 else "discharging" if value > 0 else "idle"
        return {"direction": direction}

    @property
    def native_value(self) -> float | str | None:
        d = self._d
        if d.sum_of:
            data = self.coordinator.data or {}
            if any(a not in data for a in d.sum_of):
                return None
            return round(sum(signed16(data[a], d.signed) for a in d.sum_of) * d.scale, 3)
        if d.product_of:
            data = self.coordinator.data or {}
            if any(a not in data for a, _ in d.product_of):
                return None
            product = 1
            for addr, signed in d.product_of:
                product *= signed16(data[addr], signed)
            return round(product * d.scale, 1)
        raw = self._raw
        if raw is None:
            return None
        if d.kind == "fault_text":
            codes = self._active_faults()
            if not codes:
                return self._names.common("none")
            text = "; ".join(f"[{c:02d}] {self._names.fault(c)['title']}" for c in codes)
            return text[:255]
        if d.kind == "ascii":
            data = self.coordinator.data or {}
            chars = []
            for i in range(d.words):
                byte = data[d.address + i] & 0xFF  # ważny tylko młodszy bajt
                if byte == 0:
                    break
                chars.append(chr(byte))
            return "".join(chars).strip() or None
        if d.kind == "date":
            first, second = raw & 0xFFFF, raw >> 16  # rok/miesiąc, dzień/godzina
            year, month, day, hour = first >> 8, first & 0xFF, second >> 8, second & 0xFF
            if year < 100:
                year += 2000
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return None
            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:00"
        if d.kind == "version":  # 940 -> V9.40
            return f"V{raw // 100}.{raw % 100:02d}"
        if d.kind == "version_lcd":  # 53033 -> V5.30.33
            return f"V{raw // 10000}.{(raw // 100) % 100:02d}.{raw % 100:02d}"
        if d.fault_list:
            active = [str((raw >> (16 * i)) & 0xFFFF) for i in range(d.words)
                      if (raw >> (16 * i)) & 0xFFFF]
            return ", ".join(active) if active else self._names.common("none")
        if d.options:
            option = d.options.get(raw)
            if option is not None:
                return self._names.option(d.key, option)
            return None if d.strict else f"{self._names.common('unknown')} ({raw})"
        if d.words == 1:
            raw = signed16(raw, d.signed)
        return round(raw * d.scale, 3)
