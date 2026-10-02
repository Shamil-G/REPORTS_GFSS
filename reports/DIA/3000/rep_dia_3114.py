# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3114 «Потребность» (процедура
rep_r_3114, «Форма 5»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Потребность на выплату социальных выплат из АО «ГФСС» по Республике Казахстан
в разрезе филиалов за месяц: по филиалам и отделениям число получателей и сумма
всего и по видам (потеря кормильца 0701, утрата трудоспособности 0702, потеря
работы 0703, беременность и роды 0704, уход за ребёнком 0705).

Источник - `loader.pnpd_potr` (потребность, месяц `pncp_date`), типы документа
4, 6, 7, 8, `pnsp_id > 0`, виды `07%`. Число получателей - `all_cnt` только по
документам `ridt_id = 6`, суммы - `all_sum` (как в оригинале: потребность
считается по сумме всех типов). Группировка - `rollup(филиал, отделение)`:
порядок строк как в оригинале (`order by 1, 2 nulls first`) - сначала итог
по республике («Итого по РК »), затем для каждого филиала его итог (название
филиала, жирным в HTML) и отделения. Код - код отделения, у строки итога
филиала - код филиала.

В оригинале процедура зависела от отделения пользователя (`setup.Branch`):
центральному аппарату показывалась вся республика («в разрезе филиалов»),
филиалу - его отделения. Отчёты этого приложения центральные
(см. CLAUDE.md), поэтому перенесена ветка «по Республике Казахстан»; разрез
по филиалу делается отдельным отчётом/параметром при необходимости. Закомментированные
в оригинале «недополученные суммы», казахский вариант текстов и параметры
`pridt`, `pkorr`, `pfil` (равны 0) не переносятся - оригинал их не использует.
«Форма 5» в названии не переносится (номер бланка). Подпись «Нач.отдела /
Исполнитель» под таблицей не переносится.

`pnpd_potr` в тестовой reports_test недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '3114'
report_name = ('Потребность на выплату социальных выплат из АО "Государственный '
               'фонд социального страхования"\n по Республике Казахстан \n '
               'в разрезе филиалов \n за {period} года')

_period_label = make_period_label({1: '{month} {year}'})

_CNT = 'Количество получателей (человек)'
_SUM = 'Сумма социальных выплат (тенге)'


def _pair(title, code):
    return Group(title, [Col(_CNT, f'kol{code}', 'int', 16),
                         Col(_SUM, f'sum{code}', 'money', 20)])


COLUMNS = [
    Col('Код', 'code', 'center', 8),
    Col('Наименование', 'name', 'text', 36),
    Group('Социальные выплаты', [
        _pair('Всего', '_all'),
        Group('в том числе по видам социальных выплат на случай', [
            _pair('потери кормильца ', '0701'),
            _pair('утраты трудоспособности', '0702'),
            _pair('потери работы', '0703'),
            _pair('потери дохода в связи с беременностью и родами', '0704'),
            _pair('потери дохода в связи с уходом за ребенком до одного '
                  'года', '0705'),
        ]),
    ]),
]

# :d_from - первое число месяца (pncp_date потребности - месячная дата).
STMT = """
select nvl(x.rfbn_id, x.rg) code,
       case when x.rfbn_id is not null
                 then (select s.short_name from rfbn_branch s where s.rfbn_id = x.rfbn_id)
            when x.rg is null then 'Итого по РК '
            else (select s.short_name from rfbn_branch s where s.rfbn_id = x.rg || '00')
       end name,
       x.kol0701 + x.kol0702 + x.kol0703 + x.kol0704 + x.kol0705 kol_all,
       x.sum0701 + x.sum0702 + x.sum0703 + x.sum0704 + x.sum0705 sum_all,
       x.kol0701, x.sum0701, x.kol0702, x.sum0702, x.kol0703, x.sum0703,
       x.kol0704, x.sum0704, x.kol0705, x.sum0705
  from (select substr(d.rfbn_id, 1, 2) rg,
               d.rfbn_id rfbn_id,
               sum(case when d.rfpm_id like '0701%' then d.all_sum else 0 end) sum0701,
               sum(case when d.rfpm_id like '0701%' and d.ridt_id = 6 then d.all_cnt else 0 end) kol0701,
               sum(case when d.rfpm_id like '0702%' then d.all_sum else 0 end) sum0702,
               sum(case when d.rfpm_id like '0702%' and d.ridt_id = 6 then d.all_cnt else 0 end) kol0702,
               sum(case when d.rfpm_id like '0703%' then d.all_sum else 0 end) sum0703,
               sum(case when d.rfpm_id like '0703%' and d.ridt_id = 6 then d.all_cnt else 0 end) kol0703,
               sum(case when d.rfpm_id like '0704%' then d.all_sum else 0 end) sum0704,
               sum(case when d.rfpm_id like '0704%' and d.ridt_id = 6 then d.all_cnt else 0 end) kol0704,
               sum(case when d.rfpm_id like '0705%' then d.all_sum else 0 end) sum0705,
               sum(case when d.rfpm_id like '0705%' and d.ridt_id = 6 then d.all_cnt else 0 end) kol0705
          from loader.pnpd_potr d
         where d.ridt_id in (4, 6, 7, 8)
           and d.rfbn_id like '%'
           and d.pncp_date = :d_from
           and d.rfpm_id like '07%'
           and d.pnsp_id > 0
         group by rollup(substr(d.rfbn_id, 1, 2), d.rfbn_id)) x
 order by x.rg nulls first, x.rfbn_id nulls first
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
