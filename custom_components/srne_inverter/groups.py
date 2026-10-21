"""Podział encji na urządzenia (grupy) w Home Assistant.

Główne urządzenie ("Informacje") zawiera dane o falowniku. Pozostałe grupy to osobne
urządzenia podłączone do głównego (via_device). Kolejność i nazwy zmienisz tutaj.
"""
from __future__ import annotations

# Kolejność grup = kolejność numerów w nazwach urządzeń (HA sortuje urządzenia po nazwie)
GROUP_ORDER = (
    "info",
    "grid",
    "pv",
    "battery",
    "energy",
    "schedule",
    "mode",
    "battery_settings",
    "grid_settings",
)

# Nazwy urządzeń: "info" to główne urządzenie ("<nazwa> – 1. Informacje"), pozostałe są do niego podłączone
GROUP_LABELS = {
    "info": "Informacje",
    "grid": "Sieć i wyjście",
    "pv": "PV i szyna DC",
    "battery": "Magazyn",
    "energy": "Energia",
    "schedule": "Harmonogram",
    "mode": "Tryb pracy",
    "battery_settings": "Ustawienia baterii",
    "grid_settings": "Ustawienia sieci",
}

GROUP_NUMBER = {group: i + 1 for i, group in enumerate(GROUP_ORDER)}


def _n(fmt: str, rng=(1, 2, 3)) -> set[str]:
    return {fmt.format(i) for i in rng}


_SETS: dict[str, set[str]] = {
    "info": {
        "serial_number", "firmware_build_time", "mcu1_version", "mcu2_version", "lcd_version",
        "minor_version", "hw_control_version", "hw_power_version", "protocol_version",
        "battery_type", "bms_protocol", "rs485_address",
        "temp_dcdc", "temp_dcac", "temp_transformer", "temp_ambient",
        "machine_state", "fault_codes", "fault_description", "fault_active", "restart", "settings_lock",
    },
    "grid": (
        {"grid_freq", "output_freq", "grid_power_total", "load_power_total",
         "home_power_total", "second_power_total"}
        | _n("grid_l{}_voltage") | _n("grid_l{}_current") | _n("grid_l{}_active_power")
        | _n("grid_l{}_apparent") | _n("output_l{}_voltage") | _n("output_l{}_current")
        | _n("load_l{}_current") | _n("load_l{}_power") | _n("load_l{}_apparent")
        | _n("home_l{}_power") | _n("second_l{}_power")
    ),
    "pv": {
        "pv1_voltage", "pv1_current", "pv1_power", "pv2_voltage", "pv2_current", "pv2_power",
        "pv_power_total", "pv_voltage", "bus_positive_voltage", "bus_negative_voltage",
    },
    "battery": {
        "battery_soc", "battery_voltage", "battery_current", "battery_power", "battery_temp",
        "pvac_power",
        "charge_state", "battery_soh", "battery_rated_capacity", "battery_remaining_capacity",
        "battery_cycles", "bms_voltage", "bms_current", "bms_temp", "bms_charge_limit_voltage",
        "bms_charge_limit_current", "bms_discharge_limit_current", "bms_alarm_1",
        "bms_alarm_2", "bms_protection_1", "bms_protection_2", "bms_alarm", "bms_protection",
        "battery_charge_today_kwh", "battery_discharge_today_kwh", "battery_charge_today_ah",
        "battery_discharge_today_ah", "battery_charge_total_ah", "battery_discharge_total_ah",
        "battery_grid_charge_today_ah", "battery_grid_charge_total_ah",
    },
    "energy": {
        "energy_pv_today", "energy_pv_total", "energy_export_today", "energy_export_total",
        "energy_import_today", "energy_import_total", "energy_load_today", "energy_load_total",
    },
    "schedule": (
        {"grid_charge_enable", "discharge_enable",
         "grid_charge_soc_end_1", "grid_charge_power_1",
         "grid_charge_start_1", "grid_charge_stop_1"}
        | _n("charge_start_{}", (2, 3)) | _n("charge_stop_{}", (2, 3))
        | _n("discharge_start_{}") | _n("discharge_stop_{}")
        | _n("charge_stop_soc_{}", (2, 3)) | _n("charge_stop_volt_{}")
        | _n("charge_max_power_{}", (2, 3)) | _n("discharge_stop_soc_{}")
        | _n("discharge_stop_volt_{}") | _n("discharge_max_power_{}")
        | _n("charge_grid_{}") | _n("charge_gen_{}") | _n("week_day_{}", range(7))
    ),
    "mode": {"priority_mode", "grid_mode", "battery_mode", "grid_charge_allow"},
    "battery_settings": {
        "inverter_charge_current", "grid_charge_current_max", "stop_charge_current",
        "limit_max_charge", "discharge_max_current", "discharge_start_voltage",
        "limit_discharge_sbu", "limit_recharge", "low_soc_alarm", "limit_discharge_offgrid",
        "low_voltage_delay", "discharge_stop_voltage", "charge_max_voltage", "recharge_voltage",
        "low_voltage_recovery", "low_voltage_alarm", "low_voltage_error",
        "bms_charge_limit_mode", "bms_comm", "temp_compensation",
    },
    "grid_settings": {
        "grid_sell_max_power", "grid_import_max_power", "ct_ratio", "zero_export_power",
        "reactive_power", "power_factor", "grid_standard", "grid_frequency_setting",
    },
}

GROUP_OF: dict[str, str] = {key: group for group, keys in _SETS.items() for key in keys}


def group_of(key: str) -> str:
    """Grupa dla klucza encji (nieznane trafiają do głównego urządzenia)."""
    return GROUP_OF.get(key, "info")
