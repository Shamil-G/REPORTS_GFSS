# -*- coding: utf-8 -*-
"""Матрица переходов получателей между группами за месяц (app_56, app_57).

Общий запрос двух отчётов REP_STAT_EXTEND: строка - группа получателя на начало
месяца (степень утраты трудоспособности у 0702, число иждивенцев у 0701),
столбцы - сколько человек из этой группы перешло в другую группу, плюс
прибывшие, убывшие и численность на конец месяца.

Источник - те же документы, что у Fill_F11 / app_33 (pnpd_document, ridt_id = 6,
статусы 0/1/2/3/5/7, pnsp_id > 0), а не rptb_dinamika_detail_ext: та таблица
заполнялась пакетом REP_STAT_EXTEND_DINAMIKA и замёрзла на 01.12.2021.

Группа получателя - последний символ 8-значного rfpm_id документа (07020101,
07020102, ... - как в rptb_dinamika_ext). Это допущение: у pnpd_document тот же
формат rfpm_id, что у payment_history, по которому когда-то строилась динамика;
на БД не проверялось.

Определения (однозначные, в отличие от оригинала - см. docstring app_56/57):
  cnt_old  - получателей группы g в прошлом месяце;
  gr_k     - из них в этом месяце оказались в группе k (диагональ k = g пуста);
  cnt_in   - в этом месяце есть, в прошлом не было, группа g - текущая;
  cnt_out  - в прошлом месяце была группа g, в этом получателя нет;
  cnt_now  - получателей группы g в этом месяце.
Баланс строки: cnt_now(g) = cnt_old(g) + cnt_in(g) - cnt_out(g)
                            - ушли из g в другие + пришли в g из других.

Получатель без source_id в расчёт не берётся (в Fill_F11 такие строки считались
одновременно прибывшими и убывшими).
"""

_PAY_FILTER = """d.ridt_id = 6
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
       and d.source_id is not null"""


def matrix_stmt(rfpm: str, names: list) -> str:
    """names - подписи строк по порядку групп 1..len(names).

    Бинд :d_from - первое число месяца отчёта."""
    n = len(names)
    spine = '\n    union all\n'.join(
        f"    select '{i}' g, '{name}' kat from dual"
        for i, name in enumerate(names, start=1)
    )
    cols = ',\n       '.join(
        f"case when s.g = '{k}' then null else "
        f"nvl(sum(case when a.grp_p = s.g and a.grp_c = '{k}' then a.n end), 0) "
        f"end gr{k}"
        for k in range(1, n + 1)
    )
    return f"""
with c as (
    select unique d.source_id, substr(d.rfpm_id, -1) grp
      from pnpd_document d
     where d.pncp_date = :d_from
       and substr(d.rfpm_id, 1, 4) = '{rfpm}'
       and {_PAY_FILTER}
),
p as (
    select unique d.source_id, substr(d.rfpm_id, -1) grp
      from pnpd_document d
     where d.pncp_date = add_months(:d_from, -1)
       and substr(d.rfpm_id, 1, 4) = '{rfpm}'
       and {_PAY_FILTER}
),
j as (
    select p.grp grp_p, c.grp grp_c
      from c, p
     where c.source_id = p.source_id(+)
    union all
    select p.grp, null
      from p
     where not exists (select 1 from c where c.source_id = p.source_id)
),
a as (
    select grp_p, grp_c, count(*) n
      from j
     group by grp_p, grp_c
),
s as (
{spine}
)
select s.kat,
       nvl(sum(case when a.grp_p = s.g then a.n end), 0)                     cnt_old,
       {cols},
       nvl(sum(case when a.grp_p is null and a.grp_c = s.g then a.n end), 0) cnt_in,
       nvl(sum(case when a.grp_c is null and a.grp_p = s.g then a.n end), 0) cnt_out,
       nvl(sum(case when a.grp_c = s.g then a.n end), 0)                     cnt_now
  from s, a
 group by s.g, s.kat
 order by s.g
"""
