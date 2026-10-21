"""Mapa rejestrów falownika SRNE HESP48120SH3 (wg dokumentu Modbus V2.04).

Adresy zapisane szesnastkowo, tak jak w dokumentacji SRNE (0xE026 = 57382).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorDef:
    key: str
    name: str
    address: int
    scale: float = 1.0
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    precision: int | None = None
    signed: bool = True
    slow: bool = False
    icon: str | None = None
    words: int = 1  # 2 = licznik 32-bitowy (młodsze słowo pod niższym adresem)
    options: dict[int, str] | None = None  # sensor wyliczeniowy (tekst)
    strict: bool = True  # False = nieznane wartości pokazuj jako "Nieznany (N)"
    sum_of: tuple[int, ...] = ()  # sensor wyliczany: suma wartości tych rejestrów
    # sensor wyliczany: iloczyn rejestrów ((adres, ze_znakiem), ...) razy scale
    product_of: tuple[tuple[int, bool], ...] = ()
    fault_list: bool = False  # rejestry traktowane jako lista kodów błędów (0 = brak)
    enabled_default: bool = True  # False = encja domyślnie wyłączona
    diagnostic: bool = False  # kategoria "Diagnostyka"
    kind: str | None = None  # "ascii" = tekst (młodszy bajt każdego rejestru), "date" = data produkcji


@dataclass(frozen=True)
class BinarySensorDef:
    key: str
    name: str
    address: int
    words: int = 1  # włączony, gdy którykolwiek z kolejnych rejestrów jest różny od 0
    device_class: str | None = "problem"


@dataclass(frozen=True)
class NumberDef:
    key: str
    name: str
    address: int
    minimum: float
    maximum: float
    step: float = 1
    scale: float = 1.0
    unit: str | None = None
    icon: str | None = None
    signed: bool = False  # rejestr ze znakiem (U2)
    # Dodatkowe rejestry zapisywane tą samą wartością (np. napięcie ładowania = 3 rejestry)
    mirrors: tuple[int, ...] = ()
    # Rejestr, który musi pozostać o co najmniej 1 krok poniżej zapisywanej wartości
    keep_below: int | None = None
    # Zapisywana wartość musi być o co najmniej 1 krok poniżej wartości tego rejestru
    must_be_below: int | None = None


@dataclass(frozen=True)
class SwitchDef:
    key: str
    name: str
    address: int
    on: int = 1
    off: int = 0
    icon: str | None = None


@dataclass(frozen=True)
class BitSwitchDef:
    key: str
    name: str
    address: int
    bit: int
    icon: str | None = None


@dataclass(frozen=True)
class SelectDef:
    key: str
    name: str
    address: int
    options: dict[int, str]  # wartość rejestru -> etykieta
    icon: str | None = None


@dataclass(frozen=True)
class TimeDef:
    key: str
    name: str
    address: int  # starszy bajt = godzina, młodszy = minuty


@dataclass(frozen=True)
class ButtonDef:
    key: str
    name: str
    address: int
    value: int = 1  # wartość zapisywana po naciśnięciu przycisku
    icon: str | None = None


@dataclass(frozen=True)
class LockDef:
    key: str
    name: str


# ---------------------------------------------------------------- sensory
def _v(key, name, addr, prec=1):
    return SensorDef(key, name, addr, 0.1, "V", "voltage", precision=prec)


def _a(key, name, addr):
    return SensorDef(key, name, addr, 0.1, "A", "current", precision=2)


def _w(key, name, addr):
    return SensorDef(key, name, addr, 1, "W", "power", precision=0)


def _va(key, name, addr):
    return SensorDef(key, name, addr, 1, "VA", "apparent_power", precision=0)


def _t(key, name, addr):
    return SensorDef(key, name, addr, 0.1, "°C", "temperature", precision=1)


def _kwh(key, name, addr, words=1):
    return SensorDef(key, name, addr, 0.1, "kWh", "energy", "total_increasing", 1,
                     signed=False, slow=True, words=words)


def _ah(key, name, addr, words=1):
    return SensorDef(key, name, addr, 1, "Ah", None, "total_increasing", 0,
                     signed=False, slow=True, icon="mdi:battery-charging", words=words)


# Tabela dla falowników split-phase / europejskich 8-12 kW (potwierdzone: 3 = praca z falownika).
# Wartości to klucze; etykiety w różnych językach są w names/<język>.json
MACHINE_STATE = {0: "initialization", 1: "standby", 2: "grid_operation", 3: "inverter_operation"}
CHARGE_STATE = {0: "off", 1: "quick", 2: "constant_voltage", 4: "float", 6: "li_activation", 8: "full"}


def _grid_w(key, name, addr):
    return SensorDef(key, name, addr, 1, "W", "power", precision=0)


SENSORS: tuple[SensorDef, ...] = (
    # --- Magazyn ---
    SensorDef("battery_soc", "Magazyn SOC", 256, 1, "%", "battery", precision=0),
    _v("battery_voltage", "Magazyn napięcie", 257, 2),
    _a("battery_current", "Magazyn prąd (+ rozładowanie, - ładowanie)", 258),
    # Moc magazynu = napięcie x prąd (0x101 x 0x102). Znak jak w prądzie:
    # dodatnia = rozładowanie (magazyn oddaje), ujemna = ładowanie (magazyn pobiera)
    SensorDef("battery_power", "Magazyn moc (+ rozładowanie, - ładowanie)", 257, 0.01, "W",
              "power", "measurement", 0, product_of=((257, False), (258, True)),
              icon="mdi:battery-charging-medium"),
    _t("battery_temp", "Magazyn temperatura", 259),
    # --- PV ---
    _v("pv1_voltage", "PV1 napięcie", 263, 2),
    _a("pv1_current", "PV1 prąd", 264),
    _w("pv1_power", "PV1 moc", 265),
    _w("pv_power_total", "PV moc suma", 266),
    _v("pv_voltage", "Napięcie szyny DC suma (Total nap. na Busbar)", 530, 2),
    _w("pvac_power", "Moc ładowania (PV + AC)", 270),
    _v("pv2_voltage", "PV2 napięcie", 271, 2),
    _a("pv2_current", "PV2 prąd", 272),
    _w("pv2_power", "PV2 moc", 273),
    SensorDef(
        "battery_type", "Typ baterii", 0xE004, 1, None, None, None, None,
        signed=False, slow=True, icon="mdi:battery-heart-variant",
        options={0: "user_defined", 1: "sld", 2: "fld", 3: "gel", 4: "lfp14", 5: "lfp15", 6: "lfp16",
                 7: "lfp7", 8: "lfp8", 9: "lfp9", 10: "nc7", 11: "nc8", 12: "nc13", 13: "nc14",
                 14: "no_battery"},
    ),
    # Protokół komunikacji BMS (0xE21B) - tylko do odczytu
    SensorDef(
        "bms_protocol", "Protokół kom. BMS", 0xE21B, 1, None, None, None, None,
        signed=False, slow=True, icon="mdi:battery-sync",
        options={17: "uze", 18: "pyl_can", 100: "sgp", 101: "gsl", 20: "dey", 21: "honghe"},
        strict=False,
    ),
    # --- Informacje o falowniku (ekran: Dane Falownika) ---
    _v("bus_positive_voltage", "Napięcie dodatniej szyny", 0x228),
    _v("bus_negative_voltage", "Napięcie ujemnej szyny", 0x229),
    SensorDef("serial_number", "Numer seryjny", 0x35, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:identifier", words=20, kind="ascii"),
    SensorDef("firmware_build_time", "Data kompilacji oprogramowania", 0x21, 1, None, None, None,
              None, signed=False, slow=True, diagnostic=True, icon="mdi:calendar-clock",
              words=20, kind="ascii", enabled_default=False),
    SensorDef("mcu1_version", "MCU1 wersja", 0x14, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version"),
    SensorDef("mcu2_version", "MCU2 wersja", 0x15, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version"),
    SensorDef("lcd_version", "Wersja LCD", 0x18, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version_lcd"),
    SensorDef("minor_version", "Wersja mniejsza", 0x0A, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip"),
    SensorDef("hw_control_version", "Wersja sprzętowa: panel sterowania", 0x16, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version", enabled_default=False),
    SensorDef("hw_power_version", "Wersja sprzętowa: płyta mocy", 0x17, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version", enabled_default=False),
    SensorDef("protocol_version", "Wersja protokołu Modbus", 0x1C, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:chip", kind="version", enabled_default=False),
    SensorDef("rs485_address", "Adres RS485", 0x1A, 1, None, None, None, None, signed=False,
              slow=True, diagnostic=True, icon="mdi:serial-port"),
    # --- Stan pracy i błędy ---
    SensorDef("machine_state", "Stan pracy falownika", 0x210, 1, None, None, None, None,
              signed=False, icon="mdi:state-machine", options=MACHINE_STATE, strict=False),
    SensorDef("charge_state", "Stan ładowania baterii", 0x10B, 1, None, None, None, None,
              signed=False, icon="mdi:battery-charging", options=CHARGE_STATE, strict=False),
    SensorDef("fault_codes", "Kody błędów", 0x204, 1, None, None, None, None,
              signed=False, icon="mdi:alert-circle-outline", words=4, fault_list=True),
    SensorDef("fault_description", "Opis błędów falownika", 0x204, 1, None, None, None, None,
              signed=False, icon="mdi:alert-circle", words=4, kind="fault_text"),
    # --- Bateria: SOH, pojemność, cykle ---
    SensorDef("battery_soh", "Magazyn SOH", 0x104, 1, "%", None, "measurement", 0,
              signed=False, slow=True, icon="mdi:battery-heart-variant"),
    SensorDef("battery_rated_capacity", "Pojemność znamionowa bat.", 0x105, 1, "Ah", None,
              "measurement", 0, signed=False, slow=True, icon="mdi:battery", enabled_default=False),
    SensorDef("battery_remaining_capacity", "Pozostała pojemność bat.", 0x106, 1, "Ah", None,
              "measurement", 0, signed=False, slow=True, icon="mdi:battery-medium", enabled_default=False),
    SensorDef("battery_cycles", "Liczba cykli baterii", 0x10C, 1, None, None, "total_increasing",
              0, signed=False, slow=True, icon="mdi:counter", enabled_default=False),
    # --- Dane z BMS (komunikacja CAN/RS485) ---
    SensorDef("bms_voltage", "BMS napięcie baterii", 0x112, 0.1, "V", "voltage", precision=2, signed=False),
    SensorDef("bms_current", "BMS prąd baterii", 0x113, 0.1, "A", "current", precision=2),
    SensorDef("bms_temp", "BMS temp. baterii", 0x114, 0.1, "°C", "temperature", precision=1),
    SensorDef("bms_charge_limit_voltage", "BMS napięcie ładowania bat. (limit)", 0x115, 0.1, "V",
              "voltage", precision=1, signed=False),
    SensorDef("bms_charge_limit_current", "BMS prąd ładowania baterii (limit)", 0x116, 0.1, "A",
              "current", precision=1, signed=False),
    SensorDef("bms_discharge_limit_current", "BMS prąd rozładowania baterii (limit)", 0x117, 0.1, "A",
              "current", precision=1, signed=False),
    SensorDef("bms_alarm_1", "BMS Alarmy 1", 0x118, 1, None, None, None, None, signed=False,
              diagnostic=True, icon="mdi:alert-outline"),
    SensorDef("bms_alarm_2", "BMS Alarmy 2", 0x119, 1, None, None, None, None, signed=False,
              diagnostic=True, icon="mdi:alert-outline"),
    SensorDef("bms_protection_1", "BMS Ochrona 1", 0x11A, 1, None, None, None, None, signed=False,
              diagnostic=True, icon="mdi:shield-alert-outline"),
    SensorDef("bms_protection_2", "BMS Ochrona 2", 0x11B, 1, None, None, None, None, signed=False,
              diagnostic=True, icon="mdi:shield-alert-outline"),
    # --- Moc sieci na fazach (+ oddawanie do sieci, - pobór z sieci) ---
    _grid_w("grid_l1_active_power", "GRID L1 moc czynna (+ oddawanie, - pobór)", 0x23A),
    _grid_w("grid_l2_active_power", "GRID L2 moc czynna (+ oddawanie, - pobór)", 0x23B),
    _grid_w("grid_l3_active_power", "GRID L3 moc czynna (+ oddawanie, - pobór)", 0x23C),
    SensorDef("grid_power_total", "GRID moc suma (+ oddawanie, - pobór)", 0x23A, 1, "W", "power",
              precision=0, sum_of=(0x23A, 0x23B, 0x23C)),
    _va("grid_l1_apparent", "GRID L1 moc pozorna", 0x23D),
    _va("grid_l2_apparent", "GRID L2 moc pozorna", 0x23E),
    _va("grid_l3_apparent", "GRID L3 moc pozorna", 0x23F),
    # --- Odbiory: LOAD (UPS), HOME, dodatkowe ---
    SensorDef("load_power_total", "LOAD moc suma", 539, 1, "W", "power", precision=0,
              signed=False, sum_of=(539, 562, 563)),
    SensorDef("home_l1_power", "HOME L1 moc", 0x240, 1, "W", "power", precision=0, signed=False),
    SensorDef("home_l2_power", "HOME L2 moc", 0x241, 1, "W", "power", precision=0, signed=False),
    SensorDef("home_l3_power", "HOME L3 moc", 0x242, 1, "W", "power", precision=0, signed=False),
    SensorDef("home_power_total", "HOME moc suma", 0x240, 1, "W", "power", precision=0,
              signed=False, sum_of=(0x240, 0x241, 0x242)),
    SensorDef("second_l1_power", "Odbiory dodatkowe L1 moc", 0x243, 1, "W", "power", precision=0,
              signed=False),
    SensorDef("second_l2_power", "Odbiory dodatkowe L2 moc", 0x244, 1, "W", "power", precision=0,
              signed=False),
    SensorDef("second_l3_power", "Odbiory dodatkowe L3 moc", 0x245, 1, "W", "power", precision=0,
              signed=False),
    SensorDef("second_power_total", "Odbiory dodatkowe moc suma", 0x243, 1, "W", "power",
              precision=0, signed=False, sum_of=(0x243, 0x244, 0x245)),
    # --- Ustawienia sieci (tylko do odczytu) ---
    SensorDef(
        "grid_standard", "Standard sieci", 0xE403, 1, None, None, None, None,
        signed=False, slow=True, icon="mdi:transmission-tower",
        options={2: "en_50549_1"}, strict=False,
    ),
    SensorDef(
        "grid_frequency_setting", "Częst. sieci (ustawienie)", 0xE209, 0.01, "Hz",
        "frequency", None, 0, signed=False, slow=True, icon="mdi:sine-wave",
    ),
    # --- Temperatury ---
    _t("temp_dcdc", "Temperatura PV (DC-DC)", 544),
    _t("temp_dcac", "Temperatura falownika (DC-AC)", 545),
    _t("temp_transformer", "Temperatura transformatora", 546),
    _t("temp_ambient", "Temperatura na zewnątrz (otoczenia)", 547),
    # --- Prądy ---
    _a("load_l1_current", "LOAD L1 prąd", 537),
    _a("load_l2_current", "LOAD L2 prąd", 560),
    _a("load_l3_current", "LOAD L3 prąd", 561),
    _a("grid_l1_current", "GRID L1 prąd", 532),
    _a("grid_l2_current", "GRID L2 prąd", 568),
    _a("grid_l3_current", "GRID L3 prąd", 569),
    _a("output_l1_current", "OUTPUT L1 prąd", 535),
    _a("output_l2_current", "OUTPUT L2 prąd", 558),
    _a("output_l3_current", "OUTPUT L3 prąd", 559),
    # --- Częstotliwości ---
    SensorDef("output_freq", "OUTPUT częstotliwość", 536, 0.01, "Hz", "frequency", precision=2),
    SensorDef("grid_freq", "GRID częstotliwość", 533, 0.01, "Hz", "frequency", precision=2),
    # --- Napięcia ---
    _v("output_l1_voltage", "OUTPUT L1 napięcie", 534),
    _v("output_l2_voltage", "OUTPUT L2 napięcie", 556),
    _v("output_l3_voltage", "OUTPUT L3 napięcie", 557),
    _v("grid_l1_voltage", "GRID L1 napięcie", 531),
    _v("grid_l2_voltage", "GRID L2 napięcie", 554),
    _v("grid_l3_voltage", "GRID L3 napięcie", 555),
    # --- Moc odbiorów ---
    _w("load_l1_power", "LOAD L1 moc", 539),
    _w("load_l2_power", "LOAD L2 moc", 562),
    _w("load_l3_power", "LOAD L3 moc", 563),
    _va("load_l1_apparent", "LOAD L1 moc pozorna", 540),
    _va("load_l2_apparent", "LOAD L2 moc pozorna", 564),
    _va("load_l3_apparent", "LOAD L3 moc pozorna", 565),
    # --- Energia (kWh): dzienne 16-bit, całkowite 32-bit ---
    _kwh("energy_pv_today", "Dzisiejsza produkcja PV", 61487),
    _kwh("energy_pv_total", "Całkowita produkcja PV", 61496, 2),
    _kwh("energy_export_today", "Dzisiejsza energia oddana do sieci", 61484),
    _kwh("energy_export_total", "Całkowita energia oddana do sieci", 61490, 2),
    _kwh("energy_import_today", "Dzisiejsze zużycie odbiorów z sieci", 61501),
    _kwh("energy_import_total", "Całkowite zużycie odbiorów z sieci", 61512, 2),
    _kwh("energy_load_today", "Dzisiejsze zużycie energii", 61488),
    _kwh("energy_load_total", "Całkowite zużycie energii", 61498, 2),
    _kwh("battery_charge_today_kwh", "Magazyn dzienne ładowanie", 61517),
    _kwh("battery_discharge_today_kwh", "Magazyn dzienne rozładowanie", 61518),
    # --- Ah ---
    _ah("battery_charge_today_ah", "Magazyn dzienne ładowanie Ah", 61485),
    _ah("battery_discharge_today_ah", "Magazyn dzienne rozładowanie Ah", 61486),
    _ah("battery_charge_total_ah", "Magazyn całkowite ładowanie Ah", 61492, 2),
    _ah("battery_discharge_total_ah", "Magazyn całkowite rozładowanie Ah", 61494, 2),
    _ah("battery_grid_charge_today_ah", "Magazyn dzienne ładowanie z sieci Ah", 61500),
    _ah("battery_grid_charge_total_ah", "Magazyn całkowite ładowanie z sieci Ah", 61510, 2),
)


# ------------------------------------------------- ustawienia (zapisywalne)
def _k(n: int, first_key: str | None, fmt: str) -> str:
    """Zachowuje stare klucze (unique_id) dla okresu 1."""
    return first_key if (n == 1 and first_key) else fmt.format(n)


def _series(base, key_fmt, name_fmt, minimum, maximum, step, scale, unit, icon, first_key=None):
    return tuple(
        NumberDef(_k(n, first_key, key_fmt), name_fmt.format(n), base + n - 1,
                  minimum, maximum, step, scale, unit, icon)
        for n in (1, 2, 3)
    )


# Zakresy zachowawcze - dostosuj do swojej instalacji.
NUMBERS: tuple[NumberDef, ...] = (
    # Ładowanie czasowe (okresy 1-3)
    *_series(0xE03B, "charge_stop_soc_{}", "Ładowanie okres {}: stop SOC",
             0, 100, 1, 1, "%", "mdi:battery-charging-high", "grid_charge_soc_end_1"),
    *_series(0xE041, "charge_stop_volt_{}", "Ładowanie okres {}: stop napięcie",
             40, 59.5, 0.1, 0.1, "V", "mdi:flash"),
    *_series(0xE04A, "charge_max_power_{}", "Ładowanie okres {}: maks. moc",
             0, 10000, 1, 1, "W", "mdi:transmission-tower-import", "grid_charge_power_1"),
    # Rozładowanie czasowe (okresy 1-3)
    *_series(0xE03E, "discharge_stop_soc_{}", "Rozładowanie okres {}: stop SOC",
             0, 100, 1, 1, "%", "mdi:battery-arrow-down"),
    *_series(0xE044, "discharge_stop_volt_{}", "Rozładowanie okres {}: stop napięcie",
             40, 59.5, 0.1, 0.1, "V", "mdi:flash"),
    *_series(0xE047, "discharge_max_power_{}", "Rozładowanie okres {}: maks. moc",
             0, 10000, 1, 1, "W", "mdi:transmission-tower-export"),
    # Ustawienia baterii (nazwy jak na ekranie falownika: Ustaw. Baterii)
    NumberDef("inverter_charge_current", "Maks. prąd ładowania", 0xE20A,
              0, 120, 0.1, 0.1, "A", "mdi:current-dc"),
    NumberDef("grid_charge_current_max", "Maks. prąd ład. z sieci", 0xE205,
              0, 120, 0.1, 0.1, "A", "mdi:current-ac"),
    NumberDef("stop_charge_current", "Prąd zatrzymania ład. bat.", 0xE01C,
              0, 10, 0.1, 0.1, "A", "mdi:current-dc"),
    NumberDef("limit_max_charge", "SOC zatrzymanie ład.", 0xE01D,
              0, 100, 1, 1, "%", "mdi:battery-arrow-up"),
    NumberDef("discharge_max_current", "Maks. prąd rozł. baterii", 0xE021,
              0, 200, 0.1, 0.1, "A", "mdi:current-dc"),
    NumberDef("discharge_start_voltage", "Napięcie rozpoczęcia rozł. bat.", 0xE022,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash"),
    NumberDef("limit_discharge_sbu", "SOC zatrzymanie rozł. (przejście na sieć)", 0xE01F,
              0, 100, 1, 1, "%", "mdi:battery-arrow-down"),
    NumberDef("limit_recharge", "SOC ponownego rozł. (powrót na baterię)", 0xE020,
              1, 100, 1, 1, "%", "mdi:battery-sync"),
    NumberDef("low_soc_alarm", "Alarm niska pojemność bat.", 0xE01E,
              0, 100, 1, 1, "%", "mdi:battery-alert"),
    NumberDef("limit_discharge_offgrid", "Błąd niskie SOC bat. (odcięcie rozładowania)", 0xE00F,
              0, 100, 1, 1, "%", "mdi:battery-off"),
    NumberDef("low_voltage_delay", "Opóźnienie błędu niskiego nap. baterii", 0xE010,
              0, 120, 1, 1, "s", "mdi:timer-outline"),
    # Napięcia baterii: w rejestrze w przeliczeniu na 12 V, dla baterii 48 V skala = 0.1 * 4 = 0.4 V
    NumberDef("discharge_stop_voltage", "Napięcie zatrzymania rozł. bat.", 0xE01B,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash-off"),
    # Ekran falownika zapisuje "Maks. napięcie ład." jednocześnie w 0xE007, 0xE008 i 0xE009
    # i pilnuje, by napięcie ponownego ładowania (0xE00A) było poniżej maksimum.
    NumberDef("charge_max_voltage", "Maks. napięcie ład.", 0xE007,
              48, 57.6, 0.4, 0.4, "V", "mdi:flash",
              mirrors=(0xE008, 0xE009), keep_below=0xE00A),
    # Ustawienia sieci (ekran: Ustaw. Sieci -> Podstawowe)
    NumberDef("grid_sell_max_power", "Max moc sprzedaży", 0xE400,
              0, 12000, 1, 1, "W", "mdi:transmission-tower-export"),
    # Potwierdzone odczytem: 1000 W na ekranie = 1000 w rejestrze (skala 1)
    NumberDef("grid_import_max_power", "Maks moc import", 0xE21D,
              0, 12000, 1, 1, "W", "mdi:transmission-tower-import"),
    NumberDef("ct_ratio", "Współ. zewn. CT (x : 1)", 0xE42B,
              0, 5000, 1, 1, None, "mdi:current-ac"),
    NumberDef("zero_export_power", "Moc zero-eksport", 0xE42C,
              0, 500, 1, 1, "W", "mdi:transmission-tower-off"),
    # Potwierdzone odczytem (moc bierna i PF): znak = kierunek (+ nadwzbudzenie, - niedowzbudzenie)
    NumberDef("reactive_power", "Moc bierna (+ nadwzbudzenie, - niedowzbudzenie)", 0xE402,
              -100, 100, 0.1, 0.1, "%", "mdi:flash-triangle", signed=True),
    NumberDef("power_factor", "Współczynnik mocy PF (+ nadwzbudzenie, - niedowzbudzenie)", 0xE401,
              -1, 1, 0.001, 0.001, None, "mdi:cosine-wave", signed=True),
    NumberDef("recharge_voltage", "Napięcie ponownego ład. bat.", 0xE00A,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash", must_be_below=0xE007),
    NumberDef("low_voltage_recovery", "Regeneracja baterii niskie nap.", 0xE00B,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash"),
    NumberDef("low_voltage_alarm", "Alarm niskiego poziomu nap. baterii", 0xE00C,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash-alert"),
    NumberDef("low_voltage_error", "Błąd niskiego nap. baterii", 0xE00D,
              36, 58.4, 0.4, 0.4, "V", "mdi:flash-off"),
)

SWITCHES: tuple[SwitchDef, ...] = (
    SwitchDef("grid_charge_enable", "Czasowe ładowanie włączone", 0xE02C,
              icon="mdi:transmission-tower-import"),
    SwitchDef("discharge_enable", "Czasowe rozładowanie włączone", 0xE033,
              icon="mdi:transmission-tower-export"),
    # 0xE20F (ChgSourcePriority): w menu falownika 0 = wyłączone, 1 = włączone
    SwitchDef("grid_charge_allow", "Włącz ład. sieciowe", 0xE20F,
              icon="mdi:transmission-tower-import"),
    SwitchDef("temp_compensation", "Korekta temp. prądu ładowania wł.", 0xE03A,
              icon="mdi:thermometer-lines"),
)

_DAYS = ("Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela")

BIT_SWITCHES: tuple[BitSwitchDef, ...] = (
    # Źródło ładowania czasowego (0xE04D): bit 2*(n-1) = sieć, +1 = generator
    *(
        BitSwitchDef(f"charge_grid_{n}", f"Ładowanie okres {n}: z sieci", 0xE04D,
                     2 * (n - 1), "mdi:transmission-tower")
        for n in (1, 2, 3)
    ),
    *(
        BitSwitchDef(f"charge_gen_{n}", f"Ładowanie okres {n}: z generatora", 0xE04D,
                     2 * (n - 1) + 1, "mdi:engine")
        for n in (1, 2, 3)
    ),
    # Dni tygodnia harmonogramu (0xE225): bit 0 = poniedziałek ... bit 6 = niedziela
    *(
        BitSwitchDef(f"week_day_{i}", f"Harmonogram: {day}", 0xE225, i, "mdi:calendar-week")
        for i, day in enumerate(_DAYS)
    ),
)

SELECTS: tuple[SelectDef, ...] = (
    SelectDef(
        "priority_mode", "Zarządzanie energią PV (priorytet)", 0xE039,
        {0: "load_priority", 1: "charge_priority", 2: "grid_priority"},
        "mdi:priority-high",
    ),
    SelectDef(
        "grid_mode", "Tryb sieci hybrydowy", 0xE037,
        {1: "grid_connected", 2: "limit_ups_load", 3: "limit_home_load", 4: "grid_side_coupling"},
        "mdi:transmission-tower",
    ),
    SelectDef(
        "battery_mode", "Zarządzanie energią baterii", 0xE42A,
        {0: "standby", 1: "supply_ups_loads", 2: "supply_home_loads", 3: "sell_to_grid"},
        "mdi:home-battery",
    ),
    SelectDef(
        "bms_charge_limit_mode", "Tryb ogr. prądu ład. BMS", 0xE025,
        {0: "hmi_settings", 1: "bms_protocol", 2: "inverter_logic"},
        "mdi:battery-lock",
    ),
    SelectDef(
        "bms_comm", "Komunikacja BMS", 0xE215,
        {0: "off", 1: "rs485", 2: "can"},
        "mdi:lan-connect",
    ),
)


def _times() -> tuple[TimeDef, ...]:
    out: list[TimeDef] = []
    for n in (1, 2, 3):
        out.append(TimeDef(_k(n, "grid_charge_start_1", "charge_start_{}"),
                           f"Ładowanie okres {n}: start", 0xE026 + 2 * (n - 1)))
        out.append(TimeDef(_k(n, "grid_charge_stop_1", "charge_stop_{}"),
                           f"Ładowanie okres {n}: koniec", 0xE027 + 2 * (n - 1)))
    for n in (1, 2, 3):
        out.append(TimeDef(f"discharge_start_{n}",
                           f"Rozładowanie okres {n}: start", 0xE02D + 2 * (n - 1)))
        out.append(TimeDef(f"discharge_stop_{n}",
                           f"Rozładowanie okres {n}: koniec", 0xE02E + 2 * (n - 1)))
    return tuple(out)


TIMES: tuple[TimeDef, ...] = _times()

# Blokada ustawień kodem (encja lock): zapisy od użytkowników wymagają odblokowania (kod w opcjach integracji)
LOCKS: tuple[LockDef, ...] = (LockDef("settings_lock", "Blokada ustawień"),)

# Przycisk resetu falownika: 0xDF01 CmdMachineReset (1 = reset). Wymaga hasła, jeśli jest ustawione.
BUTTONS: tuple[ButtonDef, ...] = (
    ButtonDef("restart", "Restart falownika", 0xDF01, 1, "mdi:restart"),
)


BINARY_SENSORS: tuple[BinarySensorDef, ...] = (
    BinarySensorDef("fault_active", "Błąd falownika", 0x204, 4),
    BinarySensorDef("bms_alarm", "Alarm BMS", 0x118, 2),
    BinarySensorDef("bms_protection", "Zabezpieczenie BMS", 0x11A, 2),
)


def _span(addr: int, words: int = 1) -> set[int]:
    return set(range(addr, addr + words))


SLOW_ADDRESSES: set[int] = set()
FAST_ADDRESSES: set[int] = set()
for _s in SENSORS:
    (SLOW_ADDRESSES if _s.slow else FAST_ADDRESSES).update(_span(_s.address, _s.words))
for _s in SENSORS:
    if _s.sum_of:
        (SLOW_ADDRESSES if _s.slow else FAST_ADDRESSES).update(_s.sum_of)
for _s in SENSORS:
    if _s.product_of:
        (SLOW_ADDRESSES if _s.slow else FAST_ADDRESSES).update(a for a, _ in _s.product_of)
for _b in BINARY_SENSORS:
    FAST_ADDRESSES.update(_span(_b.address, _b.words))
for _group in (NUMBERS, SWITCHES, BIT_SWITCHES, SELECTS, TIMES):
    for _d in _group:
        SLOW_ADDRESSES.add(_d.address)
ALL_ADDRESSES: set[int] = FAST_ADDRESSES | SLOW_ADDRESSES


def build_blocks(addresses: set[int], max_gap: int = 2, max_len: int = 32) -> list[tuple[int, int]]:
    """Łączy sąsiednie rejestry w bloki (start, liczba). Limit protokołu: 32 rejestry."""
    blocks: list[tuple[int, int]] = []
    start = prev = None
    for addr in sorted(addresses):
        if start is None:
            start = prev = addr
        elif addr - prev <= max_gap and addr - start + 1 <= max_len:
            prev = addr
        else:
            blocks.append((start, prev - start + 1))
            start = prev = addr
    if start is not None:
        blocks.append((start, prev - start + 1))
    return blocks
