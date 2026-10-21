"""Koordynator odpytywania falownika."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SrneClient, SrneConnectionError, SrneDeviceError, SrneError
from .const import (
    CONF_LOCK_MINUTES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOCK_MINUTES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SLOW_EVERY,
)
from .registers import ALL_ADDRESSES, FAST_ADDRESSES, SLOW_ADDRESSES, build_blocks
from .writelock import WriteLock, verify_password

_LOGGER = logging.getLogger(__name__)

PASSWORD_FLAG_REGISTER = 0x0211  # 0 = hasło niewpisane, 1 = użytkownika, 4 = producenta
PASSWORD_INPUT_REGISTER = 0xE203  # wpisanie hasła ustawień zaawansowanych
LOCK_CODES = {0x04, 0x05, 0x09, 0x0B}

ERROR_TEXT = {
    1: "polecenie nieobsługiwane",
    2: "nieprawidłowy adres rejestru",
    3: "wartość poza zakresem akceptowanym przez falownik",
    4: "operacja nieudana (parametr nie może być teraz zapisany)",
    5: "nieprawidłowe hasło",
    6: "błąd ramki",
    7: "parametr tylko do odczytu",
    8: "parametru nie można zmieniać podczas pracy",
    9: "parametr chroniony hasłem",
    11: "brak uprawnień",
}


def _describe(err: SrneError, has_password: bool) -> str:
    code = getattr(err, "code", None)
    if code is None:
        return str(err)
    text = ERROR_TEXT.get(code, f"kod błędu {code}")
    if code in (4, 5, 9, 11):
        text += (
            " - sprawdź hasło falownika"
            if has_password
            else " - odblokuj ustawienia (encja „Blokada ustawień”) hasłem falownika"
        )
    return text


class SrneCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Czyta rejestry blokami; słowniki: adres -> surowa wartość 16-bit."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SrneClient) -> None:
        interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.names = None  # ustawiane w async_setup_entry (obiekt Names)
        self.write_lock = WriteLock(entry.options.get(CONF_LOCK_MINUTES, DEFAULT_LOCK_MINUTES))
        self._relock_unsub = None
        raw_pwd = entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD, ""))
        # hasło zapisane w opcjach (opcjonalne) - używane tylko do zapisów bez użytkownika (automatyzacje)
        self._auto_password: int | None = int(raw_pwd) if str(raw_pwd).isdigit() else None
        # hasło wpisane przy odblokowaniu - tylko w pamięci, do końca czasu odblokowania
        self._password: int | None = None
        self._cycle = 0
        self._force_slow = False
        self._split: set[tuple[int, int]] = set()
        self._bad: set[int] = set()
        self._fast_blocks = build_blocks(FAST_ADDRESSES)
        self._slow_blocks = build_blocks(SLOW_ADDRESSES)

    async def _read_block(self, block: tuple[int, int], data: dict[int, int]) -> None:
        start, count = block
        if block not in self._split:
            try:
                regs = await self.client.read(start, count)
            except SrneDeviceError:
                if count == 1:
                    self._bad.add(start)
                    return
                _LOGGER.debug("Blok %s+%s odrzucony - czytam rejestry pojedynczo", start, count)
                self._split.add(block)
            else:
                data.update(zip(range(start, start + count), regs))
                return
        for addr in range(start, start + count):
            if addr not in ALL_ADDRESSES or addr in self._bad:
                continue
            try:
                regs = await self.client.read(addr, 1)
            except SrneDeviceError:
                _LOGGER.debug("Rejestr %s niedostępny - pomijam", addr)
                self._bad.add(addr)
                continue
            data[addr] = regs[0]

    async def _async_update_data(self) -> dict[int, int]:
        self._cycle += 1
        slow = self._cycle == 1 or self._force_slow or self._cycle % SLOW_EVERY == 0
        self._force_slow = False
        blocks = list(self._fast_blocks) + (self._slow_blocks if slow else [])
        data = dict(self.data or {})
        try:
            for block in blocks:
                await self._read_block(block, data)
        except SrneConnectionError as err:
            raise UpdateFailed(f"Błąd komunikacji z falownikiem: {err}") from err
        return data

    @property
    def _active_password(self) -> int | None:
        """Hasło z odblokowania (jeśli trwa), w przeciwnym razie opcjonalne hasło dla automatyzacji."""
        if self._password is not None:
            if self.write_lock.unlocked:
                return self._password
            self._password = None
        return self._auto_password

    async def _ensure_unlocked(self) -> None:
        """Wpisuje hasło ustawień zaawansowanych, jeśli falownik jest zablokowany."""
        password = self._active_password
        if password is None:
            return
        try:
            if (await self.client.read(PASSWORD_FLAG_REGISTER, 1))[0] in (1, 4):
                return
        except SrneDeviceError:
            pass
        await self.client.write(PASSWORD_INPUT_REGISTER, password)

    async def _write_register(self, address: int, value: int) -> None:
        _LOGGER.debug("Zapis rejestru %s = %s", hex(address), value)
        await self._ensure_unlocked()
        try:
            await self.client.write(address, value)
        except SrneDeviceError as err:
            password = self._active_password
            if password is None or err.code not in LOCK_CODES:
                raise
            # blokada mogła wygasnąć - wpisz hasło ponownie i spróbuj jeszcze raz
            await self.client.write(PASSWORD_INPUT_REGISTER, password)
            await self.client.write(address, value)

    async def async_write(self, address: int, value: int) -> None:
        """Zapis pojedynczego rejestru + natychmiastowe odświeżenie."""
        await self.async_write_many([(address, value)])

    async def async_write_many(self, writes: list[tuple[int, int]]) -> None:
        """Zapis kilku rejestrów po kolei (w podanej kolejności) + odświeżenie."""
        try:
            for address, value in writes:
                await self._write_register(address, value)
        except SrneError as err:
            raise HomeAssistantError(
                f"Zapis do falownika nie powiódł się: {_describe(err, self._active_password is not None)}"
            ) from err
        self._force_slow = True
        self.async_set_updated_data({**(self.data or {}), **dict(writes)})
        await self.async_request_refresh()

    async def async_write_bit(self, address: int, bit: int, on: bool) -> None:
        """Zmiana jednego bitu rejestru-maski bez ruszania pozostałych."""
        try:
            current = (await self.client.read(address, 1))[0]
        except SrneError as err:
            raise HomeAssistantError(f"Odczyt przed zapisem nie powiódł się: {err}") from err
        new = (current | (1 << bit)) if on else (current & ~(1 << bit))
        await self.async_write(address, new & 0xFFFF)

    async def async_read_range(self, start: int, count: int) -> dict[int, int | None]:
        """Odczyt zakresu rejestrów (do diagnostyki); niedostępne -> None."""
        result: dict[int, int | None] = {}
        pos, end = start, start + count
        while pos < end:
            n = min(32, end - pos)
            try:
                regs = await self.client.read(pos, n)
                result.update(zip(range(pos, pos + n), regs))
            except SrneDeviceError:
                for addr in range(pos, pos + n):
                    try:
                        result[addr] = (await self.client.read(addr, 1))[0]
                    except SrneDeviceError:
                        result[addr] = None
            pos += n
        return result

    # ------------------------------------------------------------------ blokada ustawień (kod)
    def ensure_writable(self, context=None) -> None:
        """Zapisy od użytkownika (UI, aplikacja) wymagają odblokowania; automatyzacje (bez użytkownika) przechodzą."""
        if not self.write_lock.allows(getattr(context, "user_id", None)):
            raise ServiceValidationError(
                "Ustawienia falownika są zablokowane. Odblokuj je kodem (encja „Blokada ustawień”)."
            )

    async def async_unlock(self, code: str | None) -> None:
        """Odblokowanie hasłem falownika: weryfikacja w falowniku, hasło tylko w pamięci na czas odblokowania."""
        if self.write_lock.attempts_blocked:
            raise ServiceValidationError(
                f"Zbyt wiele błędnych prób. Spróbuj ponownie za {self.write_lock.blocked_seconds} s."
            )
        text = str(code or "").strip()
        password = int(text) if text.isdigit() and int(text) <= 65535 else None
        ok = False
        if password is not None:
            try:
                ok = await verify_password(self.client.read, self.client.write, password, SrneDeviceError)
            except SrneError as err:
                raise ServiceValidationError(
                    f"Nie można zweryfikować hasła - brak komunikacji z falownikiem ({err})."
                ) from err
        if not ok:
            if self.write_lock.fail() == "blocked":
                raise ServiceValidationError(
                    f"Zbyt wiele błędnych prób. Spróbuj ponownie za {self.write_lock.blocked_seconds} s."
                )
            raise ServiceValidationError("Nieprawidłowe hasło.")
        self._password = password
        self.write_lock.grant()
        self._cancel_relock()
        self._relock_unsub = async_call_later(self.hass, self.write_lock.remaining + 1, self._relock_expired)
        self.async_update_listeners()

    @callback
    def async_lock(self) -> None:
        self.write_lock.lock()
        self._password = None
        self._cancel_relock()
        self.async_update_listeners()

    @callback
    def _relock_expired(self, _now) -> None:
        self._relock_unsub = None
        self._password = None
        self.async_update_listeners()

    def _cancel_relock(self) -> None:
        if self._relock_unsub is not None:
            self._relock_unsub()
            self._relock_unsub = None

    async def async_shutdown(self) -> None:
        self._password = None
        self._cancel_relock()
        await super().async_shutdown()
