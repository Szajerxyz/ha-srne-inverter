"""Stałe integracji SRNE Inverter."""

DOMAIN = "srne_inverter"

CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PASSWORD = "password"
CONF_LOCK_CODE = "lock_code"
CONF_LOCK_MINUTES = "lock_minutes"
DEFAULT_LOCK_MINUTES = 10

DEFAULT_NAME = "Falownik SRNE"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 5  # sekundy

# Rejestry "wolne" (liczniki energii, ustawienia) czytane co N cykli
SLOW_EVERY = 6

MANUFACTURER = "SRNE"
MODEL = "HESP48120SH3"
