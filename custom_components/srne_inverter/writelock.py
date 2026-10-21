"""Blokada zapisu ustawień - czysta logika (bez zależności od Home Assistant).

Hasło falownika nie jest przechowywane: użytkownik wpisuje je przy odblokowaniu,
a integracja trzyma je tylko w pamięci do końca czasu odblokowania.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

MAX_FAILS = 5  # tyle błędnych prób z rzędu uruchamia czasową blokadę prób
LOCKOUT_SECONDS = 60

PASSWORD_SET_REGISTER = 0xE202  # ustawione hasło (w tym falowniku daje się odczytać)
PASSWORD_INPUT_REGISTER = 0xE203  # wpisanie hasła
PASSWORD_FLAG_REGISTER = 0x0211  # 0 = niewpisane, 1 = użytkownika, 4 = producenta


class WriteLock:
    """Stan blokady: zapisy od użytkowników są dozwolone tylko po odblokowaniu (na N minut).

    Zapisy bez użytkownika (automatyzacje, system) nie są blokowane przez tę klasę.
    """

    def __init__(self, minutes: int = 10, clock: Callable[[], float] = time.monotonic) -> None:
        self._minutes = max(1, int(minutes))
        self._clock = clock
        self._until = 0.0
        self._fails = 0
        self._blocked_until = 0.0

    @property
    def unlocked(self) -> bool:
        return self._clock() < self._until

    @property
    def remaining(self) -> int:
        """Sekundy do ponownego zablokowania (0, gdy zablokowane)."""
        return max(0, int(self._until - self._clock() + 0.999))

    @property
    def attempts_blocked(self) -> bool:
        return self._clock() < self._blocked_until

    @property
    def blocked_seconds(self) -> int:
        return max(0, int(self._blocked_until - self._clock() + 0.999))

    def fail(self) -> str:
        """Zapisuje błędną próbę. Zwraca "bad" albo "blocked" (po MAX_FAILS próbach z rzędu)."""
        self._fails += 1
        if self._fails >= MAX_FAILS:
            self._fails = 0
            self._blocked_until = self._clock() + LOCKOUT_SECONDS
            return "blocked"
        return "bad"

    def grant(self) -> None:
        """Poprawne hasło: odblokuj na ustawiony czas i wyzeruj licznik błędów."""
        self._fails = 0
        self._until = self._clock() + self._minutes * 60

    def lock(self) -> None:
        self._until = 0.0

    def allows(self, user_id: str | None) -> bool:
        """Zapis dozwolony, gdy odblokowano albo polecenie nie pochodzi od użytkownika."""
        return self.unlocked or user_id is None


async def verify_password(
    read: Callable[[int, int], Awaitable[list[int]]],
    write: Callable[[int, int], Awaitable[None]],
    password: int,
    device_error: type[Exception],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    retries: int = 3,
) -> bool:
    """Sprawdza hasło bez jego przechowywania.

    1. Porównanie z hasłem ustawionym w falowniku (rejestr 0xE202) - bez zapisu do falownika.
       Wartość 0 oznacza falownik bez hasła (każdy kod jest akceptowany).
    2. Gdy tego rejestru nie da się odczytać: wpisanie hasła do 0xE203 i kontrola flagi 0x0211.
    Błędy komunikacji (nie-"device_error") są przekazywane wyżej.
    """
    try:
        stored = (await read(PASSWORD_SET_REGISTER, 1))[0]
    except device_error:
        stored = None
    if stored is not None:
        return stored == 0 or stored == password
    try:
        await write(PASSWORD_INPUT_REGISTER, password)
    except device_error:
        return False
    for _ in range(retries):
        await sleep(0.2)
        try:
            if (await read(PASSWORD_FLAG_REGISTER, 1))[0] in (1, 4):
                return True
        except device_error:
            return False
    return False
