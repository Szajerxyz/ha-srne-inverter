"""Integracja SRNE Inverter (Modbus TCP przez konwerter RS485)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .client import SrneClient, SrneError
from .const import CONF_SLAVE, DOMAIN, MANUFACTURER, MODEL
from .coordinator import SrneCoordinator
from .entity import device_name
from .names import Names
from .registers import (
    BINARY_SENSORS,
    BIT_SWITCHES,
    BUTTONS,
    LOCKS,
    NUMBERS,
    SELECTS,
    SENSORS,
    SWITCHES,
    TIMES,
)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_READ_REGISTERS = "read_registers"
READ_SCHEMA = vol.Schema(
    {
        vol.Required("start"): vol.Any(int, str),
        vol.Optional("count", default=16): vol.All(vol.Coerce(int), vol.Range(min=1, max=128)),
        vol.Optional("config_entry_id"): str,
    }
)

type SrneConfigEntry = ConfigEntry[SrneCoordinator]


def _all_entities():
    """(domena, klucz, domyślnie wyłączona) dla wszystkich encji integracji."""
    for d in SENSORS:
        yield "sensor", d.key, not d.enabled_default
    for d in BINARY_SENSORS:
        yield "binary_sensor", d.key, False
    for d in NUMBERS:
        yield "number", d.key, False
    for d in (*SWITCHES, *BIT_SWITCHES):
        yield "switch", d.key, False
    for d in SELECTS:
        yield "select", d.key, False
    for d in TIMES:
        yield "time", d.key, False
    for d in BUTTONS:
        yield "button", d.key, False
    for d in LOCKS:
        yield "lock", d.key, False


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """v1 -> v2: nowe, angielskie ID encji (srne_<id> z names/en.json)."""
    if entry.version < 2:
        names = await Names.async_load(hass)
        registry = er.async_get(hass)
        for domain, key, _ in _all_entities():
            object_id = names.object_id(key)
            current = registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}")
            desired = f"{domain}.srne_{object_id}"
            if object_id and current and current != desired and registry.async_get(desired) is None:
                registry.async_update_entity(current, new_entity_id=desired)
        hass.config_entries.async_update_entry(entry, version=2)
    if entry.version < 3:
        # v3: kodem odblokowania jest hasło falownika (nie jest przechowywane); stary kod blokady nieużywany
        options = {k: v for k, v in entry.options.items() if k != "lock_code"}
        hass.config_entries.async_update_entry(entry, options=options, version=3)
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def _read_registers(call: ServiceCall) -> dict:
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
            and call.data.get("config_entry_id") in (None, e.entry_id)
        ]
        if len(entries) != 1:
            raise ServiceValidationError(
                "Podaj config_entry_id (znaleziono "
                f"{len(entries)} aktywnych falowników)"
            )
        try:
            start = int(str(call.data["start"]), 0)  # np. 57388 lub 0xE02C
        except ValueError as err:
            raise ServiceValidationError("Nieprawidłowy adres startowy") from err
        try:
            regs = await entries[0].runtime_data.async_read_range(start, call.data["count"])
        except SrneError as err:
            raise HomeAssistantError(f"Błąd odczytu: {err}") from err
        return {"registers": {f"0x{a:04X} ({a})": v for a, v in regs.items()}}

    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_REGISTERS,
        _read_registers,
        schema=READ_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SrneConfigEntry) -> bool:
    client = SrneClient(entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_SLAVE])
    coordinator = SrneCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise
    coordinator.names = await Names.async_load(hass)
    entry.runtime_data = coordinator
    # angielskie ID encji: rejestracja z góry, niezależnie od języka i nazw urządzeń
    registry = er.async_get(hass)
    for domain, key, disabled in _all_entities():
        object_id = coordinator.names.object_id(key)
        if object_id:
            registry.async_get_or_create(
                domain,
                DOMAIN,
                f"{entry.entry_id}_{key}",
                suggested_object_id=f"srne_{object_id}",
                config_entry=entry,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION if disabled else None,
            )
    # główne urządzenie musi istnieć przed podurządzeniami (via_device)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name(entry, "info", coordinator.names),
        manufacturer=MANUFACTURER,
        model=MODEL,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_update))
    return True


async def _reload_on_update(hass: HomeAssistant, entry: SrneConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SrneConfigEntry) -> bool:
    if ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return ok
