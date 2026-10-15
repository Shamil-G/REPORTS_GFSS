# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3015 (процедура REP_R_3015).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Число получателей социальных выплат по областям, имеющих статус оралмана
(карточки `om_card` / `om_person`, сопоставление с `person` по фамилии, имени
и отчеству), с выплатами за период (`pnpd_document`, `rfpm_id like '07%'`,
типы выплаты 4, 6, 7, 8, статусы 0-3, 5, 7, `pnsp_id > 0`). Область -
по последней выплате человека за период (первые две цифры отделения),
название - `branch.name` по коду `<область>00` (в оригинале
`rfrg_region.name`, у него казахские буквы подменены). Колонки: всего и по
видам 0701-0705.

Оригинал выбирал в подзапросе `pp.rn` (в запрос идёт только ради
`person.rn`; в итоге не используется) - из запроса убран, остальное без
изменений. Имя отчёта: «оплучателей» (опечатка) исправлено на «получателей».

Причина невалидности процедуры в боевой БД - `ORA-00904: "PP.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `pp.iin`. Период: `pncp_date between` заменён на `pncp_date >= :d_from and pncp_date < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `om_card`, `om_person` лежат в SSWH, reports_test их не видит: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3015'
report_name = 'Сведения о числе получателей СВ, присвоенных статус оралмана, с {date_from} по {date_to} года'

COLUMNS = [
    Col('Регион', 'name', 'text', 30),
    Col('Всего', 'cnt', 'int', 12),
    Col('По потере кормильца', 'r0701', 'int', 14),
    Col('По утрате трудоспособности', 'r0702', 'int', 14),
    Col('По потере работы', 'r0703', 'int', 14),
    Col('По беременности и родам', 'r0704', 'int', 14),
    Col('Соцвыплаты по уходу за ребенком до года', 'r0705', 'int', 16),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select b.name,
       count(unique sicid) cnt,
       count(unique case when rfpm = '0701' then sicid end) r0701,
       count(unique case when rfpm = '0702' then sicid end) r0702,
       count(unique case when rfpm = '0703' then sicid end) r0703,
       count(unique case when rfpm = '0704' then sicid end) r0704,
       count(unique case when rfpm = '0705' then sicid end) r0705
  from (select pp.sicid, substr(pd.rfpm_id, 1, 4) rfpm, pd.pncd_id,
               first_value(substr(pd.rfbn_id, 1, 2))
                 over (partition by pd.pncd_id order by pd.pncp_date desc) reg
          from om_card d
         inner join om_person p on d.id = p.car_id
         inner join person pp on p.surname = pp.lastname
                             and p.name = pp.firstname
                             and p.patronymic = pp.middlename
         inner join pnpd_document pd
            on pp.sicid = pd.pncd_id
           and pd.pncp_date >= :d_from and pd.pncp_date < :d_to
           and pd.rfpm_id like '07%'
           and pd.ridt_id in (4, 6, 7, 8)
           and pd.status in (0, 1, 2, 3, 5, 7)
           and pd.pnsp_id > 0) d,
       branch b
 where d.reg || '00' = b.rfbn_id
 group by b.name
 order by b.name
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
