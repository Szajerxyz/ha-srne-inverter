# SRNE Inverter – integracja Home Assistant Waveshare RS485 TO ETH (B) (Modbus TCP)

Falownik SRNE HESP48120SH3 jako urządzenie w Home Assistant, bez wpisów w `configuration.yaml`.
Komunikacja: falownik → RS485 → Waveshare (tryb **Modbus TCP ↔ RTU**) → Home Assistant.

## Instalacja przez HACS
1. HACS → ⋮ → *Custom repositories* → adres `https://github.com/Szajerxyz/ha-srne-inverter`, kategoria **Integration**.
2. Pobierz „SRNE Inverter”, zrestartuj Home Assistant.
3. *Ustawienia → Urządzenia i usługi → Dodaj integrację → SRNE Inverter*.

## Instalacja ręczna
Skopiuj `custom_components/srne_inverter` do `/config/custom_components/`, zrestartuj HA, dodaj integrację.


## Hasło ustawień zaawansowanych
Część parametrów falownik pozwala zmieniać dopiero po wpisaniu hasła. Domyślnie integracja **nie przechowuje**
tego hasła – wpisujesz je przy odblokowaniu ustawień (patrz niżej). Jeśli automatyzacje mają zmieniać ustawienia bez odblokowywania,
wpisz hasło w *Ustawienia → Urządzenia i usługi → SRNE Inverter → Konfiguruj* (jest wtedy przechowywane w konfiguracji HA).

## Blokada ustawień (hasło falownika wpisywane przy odblokowaniu)
Zapisy wykonywane przez **użytkowników** (dashboard, aplikacja, ręcznie uruchamiane skrypty) są odrzucane, dopóki ustawienia
nie zostaną odblokowane w encji `lock.srne_settings_lock` („Blokada ustawień”): dotknij jej i wpisz **hasło ustawień
zaawansowanych falownika** (do 5 cyfr).
- Hasło **nie jest przechowywane** w integracji: jest sprawdzane w falowniku (rejestr 0xE202; gdy go nie da się odczytać – przez
  wpisanie do 0xE203 i kontrolę flagi 0x0211), trzymane tylko w pamięci i usuwane po upływie czasu odblokowania.
- Czas odblokowania (domyślnie 10 min) ustawia się w *Konfiguruj*. Po restarcie HA ustawienia są zawsze zablokowane.
- Zapisy z **automatyzacji** (bez użytkownika) nie są blokowane przez integrację, ale falownik wymaga hasła do chronionych
  parametrów. Jeśli automatyzacje mają działać bez odblokowywania, wpisz w *Konfiguruj* opcjonalne „Hasło falownika dla
  automatyzacji” (wtedy jest przechowywane w konfiguracji HA).
- Po 5 błędnych hasłach z rzędu kolejne próby są wstrzymane na 60 s. Falownik bez ustawionego hasła (wartość 0) akceptuje dowolny kod.

## Pliki srne_lcd_theme oraz dashboard_srne_lcd_widoki zawierają przykład dashbordu dla integracji

Motyw "SRNE LCD" - ciemny, w stylu ekranu falownika SRNE
Instalacja: skopiuj do /config/themes/srne_lcd.yaml, w configuration.yaml dodaj:
  frontend:
  themes: !include_dir_merge_named themes
i wykonaj: Narzędzia deweloperskie -> YAML -> Przeładuj motywy (albo restart HA).

===== SRNE LCD v2: jedna zakładka + podwidoki (PV, Sieć, Magazyn, Odbiory, Falownik z ustawieniami) =====
Wymagane: motyw "SRNE LCD" (srne_lcd_theme.yaml) oraz HACS: button-card, mushroom, apexcharts-card, modern-circular-gauge.
Dopisz na końcu listy `views:` w surowym edytorze konfiguracji (wcięcie 2 spacje).
Podwidoki (subview: true) nie są pokazywane na pasku zakładek - otwiera się je kliknięciem w kafelek.
