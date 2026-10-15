# -*- coding: utf-8 -*-
"""Проверка доступа к отчётам по человеку (ИИН) до формирования отчёта.

Подставляется как `check_params` в `build_report`. Исключения текстом идут
пользователю и в журнал доступа (`util.access_audit`):
  - неверная длина ИИН;
  - человека нет в `person` -> `ValueError('Участник не найден!')`;
  - ИИН есть в Active Directory у действующего сотрудника (`util.ad_check`) ->
    `ValueError('Доступ запрещен!')`: данные сотрудников не выдаются;
  - AD недоступен -> `AdUnavailable` (не `ValueError`): отчёт не выдаётся,
    в журнал пишется ОШИБКА (доступ не открывается по неполным данным).

Раньше доступ закрывался таблицей `notobor` (список СИК, который вели вручную,
`P_ALL_INFO`); решение Шамиля 15.10.2026 - проверять по AD.
"""
from db.connect import select_2, LOADER_PROFILE
from util.ad_check import iin_in_ad


def check_person_access(params):
    iin = str(params.get('iin') or '').strip()
    if len(iin) != 12 or not iin.isdigit():
        raise ValueError('Неверно указан ИИН!')
    rows = select_2('select 1 from person where iin = :iin',
                    {'iin': iin}, profile=LOADER_PROFILE, raise_on_error=True)
    if not rows:
        raise ValueError('Участник не найден!')
    if iin_in_ad(iin):
        raise ValueError('Доступ запрещен!')
