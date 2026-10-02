# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 8 (процедура rep_r_8).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сравнительный анализ получателей социальных выплат и государственных
социальных пособий (ГСП) на текущую дату: по регионам число получателей
пособий (ГСП) по потере кормильца (0202) и по утрате трудоспособности (0201)
и число получателей СВ из ГФСС по тем же случаям (0701 и 0702) среди
лиц пенсионного возраста.

Источник - `pnpt_payment` + `person`, действующие выплаты
(`date_close is null`), коды пособий `020124`, `020125`, `020132`, `020236`-`020240`
исключены; признак пенсионного возраста - функция схемы SSWH `pens_vozr`
(`= 1`). Название региона - `s_region_name2` (тоже функция SSWH). Итоговая
строка - `grouping sets (1, (регион, название))`, название итога - «Всего».

Параметров нет; дата в названии - дата формирования (`sysdate` в оригинале).
Название дословно, двойной пробел перед «и ГСП» убран. Соответствие
колонок - по `Rep.td` оригинала: ГСП по потере кормильца - `cnt_uk` (0202), из
ГФСС - `cnt_uk_s` (0701); ГСП по утрате трудоспособности - `cnt_inv` (0201),
из ГФСС - `cnt_inv_s` (0702). `<br>` в заголовках заменены пробелами.

`pens_vozr` и `s_region_name2` в тестовой reports_test недоступны: на данных
отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '8'
report_name = ('Сравнительный анализ получателей социальных выплат и ГСП '
               'на {today} г.')

COLUMNS = [
    Col('Код региона', 'reg', 'center', 10),
    Col('Регион', 'r_name', 'text', 36),
    Group('По потере кормильца', [
        Col('ГСП', 'cnt_uk', 'int', 14),
        Col('из ГФСС', 'cnt_uk_s', 'int', 14),
    ]),
    Group('По утрате трудоспособности', [
        Col('ГСП', 'cnt_inv', 'int', 14),
        Col('из ГФСС', 'cnt_inv_s', 'int', 14),
    ]),
]

STMT = """
select /*+first_rows*/
       substr(pt.rfbn_id, 1, 2) reg,
       case when s_region_name2(pt.rfbn_id) is null then 'Всего'
            else s_region_name2(pt.rfbn_id) end r_name,
       count(case when substr(pt.rfpm_id, 1, 4) in ('0202') then pt.pnpt_id else null end) cnt_uk,
       count(case when substr(pt.rfpm_id, 1, 4) in ('0701') then pt.pnpt_id else null end) cnt_uk_s,
       count(case when substr(pt.rfpm_id, 1, 4) in ('0201') then pt.pnpt_id else null end) cnt_inv,
       count(case when substr(pt.rfpm_id, 1, 4) in ('0702') then pt.pnpt_id else null end) cnt_inv_s
  from pnpt_payment pt, person p
 where pt.pncd_id = p.sicid
   and substr(pt.rfpm_id, 1, 4) in ('0201', '0202', '0701', '0702')
   and substr(pt.rfpm_id, 1, 6) not in ('020124', '020125', '020132', '020236',
                                        '020237', '020238', '020239', '020240')
   and pens_vozr(p.sicid) = 1
   and pt.date_close is null
 group by grouping sets (1, (substr(pt.rfbn_id, 1, 2), s_region_name2(pt.rfbn_id)))
 order by 1 nulls last
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE,
)
