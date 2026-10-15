# -*- coding: utf-8 -*-
"""Проверка доступа к отчётам по человеку (ИИН) до формирования отчёта.

Подставляется как `check_params` в `build_report`. Исключения (`ValueError`)
текстом идут пользователю и в журнал доступа (`util.access_audit`):
  - неверная длина ИИН;
  - человека нет в `person`;
  - человек в списке запрета `notobor` - «Доступ запрещен!» (как в
    процедуре AIS `p_all_info`).
"""
from db.connect import select_2, LOADER_PROFILE


def check_person_access(params):
    iin = str(params.get('iin') or '').strip()
    if len(iin) != 12:
        raise ValueError('Неверно указан ИИН!')
    rows = select_2("""
        select (select count(*) from notobor n where n.sicid = p.sicid) closed
          from person p
         where p.iin = :iin""", {'iin': iin}, profile=LOADER_PROFILE,
                    raise_on_error=True)
    if not rows:
        raise ValueError('Участник не найден!')
    if any(r['closed'] for r in rows):
        raise ValueError('Доступ запрещен!')
