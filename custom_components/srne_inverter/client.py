"""Cienka warstwa nad pymodbus: jedno połączenie, jedna blokada na szynie RS485."""
from __future__ import annotations

import asyncio
import inspect
import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)


class SrneError(Exception):
    """Bazowy błąd."""


class SrneConnectionError(SrneError):
    """Brak połączenia / timeout."""


class SrneDeviceError(SrneError):
    """Falownik odpowiedział wyjątkiem Modbus (np. nieistniejący rejestr)."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class SrneClient:
    """Klient Modbus TCP (konwerter Waveshare w trybie Modbus TCP <-> RTU)."""

    def __init__(self, host: str, port: int, slave: int, timeout: float = 3) -> None:
        self._slave = slave
        self._lock = asyncio.Lock()
        self._client = AsyncModbusTcpClient(host, port=port, timeout=timeout, retries=2)
        params = inspect.signature(self._client.read_holding_registers).parameters
        # pymodbus >= 3.10 używa device_id, starsze slave
        self._id_kw = "device_id" if "device_id" in params else "slave"

    async def _ensure_connected(self) -> None:
        if self._client.connected:
            return
        try:
            await self._client.connect()
        except (OSError, ModbusException, asyncio.TimeoutError) as err:
            raise SrneConnectionError(str(err)) from err
        if not self._client.connected:
            raise SrneConnectionError("Nie można nawiązać połączenia")

    async def close(self) -> None:
        res = self._client.close()
        if inspect.isawaitable(res):
            await res

    async def connect(self) -> None:
        async with self._lock:
            await self._ensure_connected()

    async def read(self, start: int, count: int) -> list[int]:
        async with self._lock:
            await self._ensure_connected()
            try:
                rr = await self._client.read_holding_registers(
                    start, count=count, **{self._id_kw: self._slave}
                )
            except (OSError, ModbusException, asyncio.TimeoutError) as err:
                await self.close()
                raise SrneConnectionError(str(err)) from err
            if rr.isError():
                if hasattr(rr, "exception_code"):
                    raise SrneDeviceError(
                        f"Wyjątek {rr.exception_code} dla {start}+{count}", rr.exception_code
                    )
                await self.close()
                raise SrneConnectionError(f"Błąd odczytu {start}+{count}: {rr}")
            await asyncio.sleep(0.03)
            return list(rr.registers)

    async def write(self, address: int, value: int) -> None:
        async with self._lock:
            await self._ensure_connected()
            try:
                rr = await self._client.write_register(
                    address, value, **{self._id_kw: self._slave}
                )
            except (OSError, ModbusException, asyncio.TimeoutError) as err:
                await self.close()
                raise SrneConnectionError(str(err)) from err
            if rr.isError():
                code = getattr(rr, "exception_code", None)
                if code is None:
                    await self.close()
                    raise SrneConnectionError(f"Błąd zapisu {address}: {rr}")
                raise SrneDeviceError(f"Zapis {address}={value} odrzucony (kod {code})", code)
            await asyncio.sleep(0.03)
