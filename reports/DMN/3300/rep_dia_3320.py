# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3320 (процедура REP_R_3320).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Список лиц, зарегистрированных в качестве безработного центром занятости
населения, с признаком участия в системе соцстрахования и делом на СВпр.

Источник - `sswh.v_lm_unemploy_ss_info` (регистрации в ЦЗ); к ней по
(ИИН, дата регистрации) присоединяется `unemployed_calc` (расчёт: есть ли
социальные отчисления `so`, размер `sum_calc`), к расчёту - макет первого
назначения `v_sipr_maket_first_approve_dn` по (человек, дата риска = дата
регистрации). Оба соединения внешние: лицо без расчёта или без дела остаётся
в списке.

В оригинале это два `left join ... on`. Старый синтаксис `(+)` не позволяет
внешне соединить одну таблицу с двумя (макет связан и с расчётом, и с
регистрацией: ORA-01417), поэтому первая пара собрана в подзапросе `ux`,
а макет присоединяется к нему одним внешним соединением.

Колонки - из `SetPageHead` (в `AddCol` оригинала лишняя «Код отделения»,
которую данные не печатали). «Участник системы СС» - «Да», если у расчёта
`so > 0`. Сортировка как в оригинале, `order by 1, 6`: код ЦЗ и дата
регистрации (шестая колонка запроса).

Название: «с» перед датой кириллическая (в оригинале латинская «c»).

`v_lm_unemploy_ss_info`, `unemployed_calc` и `v_sipr_maket_first_approve_dn`
в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3320'
report_name = ('Список лиц, зарегистрированных в качестве безработного '
               'центром занятости населения с {period} года')

COLUMNS = [
    Col('Код центра занятости', 'departamentcode', 'center', 16),
    Col('Наименование кода центра занятости', 'departamentrname', 'text', 36),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Дата регистрации в ЦЗ', 'regdate', 'date', 14),
    Col('Дата снятия с регистрации в ЦЗ', 'regclosedate', 'date', 16),
    Col('Код статуса заявителя ЦЗ', 'unemployedcategorycode', 'center', 14),
    Col('Статус заявителя ЦЗ', 'unemployedcategoryrname', 'text', 30),
    Col('Участник системы СС', 'has_so', 'center', 14),
    Col('Номер дела в СС', 'z_numb', 'center', 16),
    Col('Вид выплаты в СС', 'rfpm_id', 'center', 12),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Статус дела в СС', 'st', 'center', 12),
    Col('Источник', 'id_sour', 'center', 10),
    Col('Сумма', 'sum_calc', 'money', 16),
]

# :d_from / :d_to - период из формы (дата регистрации), :d_to исключительная.
STMT = """
with ux as (
    select u.departamentcode, u.departamentrname, u.iin,
           u.lastname || ' ' || u.firstname || ' ' || u.middlename fio,
           u.birthdate, u.regdate, u.regclosedate,
           u.unemployedcategorycode, u.unemployedcategoryrname,
           uc.so, uc.sicid, uc.sum_calc
      from sswh.v_lm_unemploy_ss_info u, unemployed_calc uc
     where u.regdate >= :d_from
       and u.regdate <  :d_to
       and u.iin     = uc.iin(+)
       and u.regdate = uc.regdate(+)
)
select ux.departamentcode,
       ux.departamentrname,
       ux.iin,
       ux.fio,
       ux.birthdate,
       ux.regdate,
       ux.regclosedate,
       ux.unemployedcategorycode,
       ux.unemployedcategoryrname,
       case when ux.so > 0 then 'Да' else 'Нет' end has_so,
       sfa.z_numb,
       sfa.rfpm_id,
       sfa.risk_date,
       sfa.st,
       sfa.id_sour,
       ux.sum_calc
  from ux, v_sipr_maket_first_approve_dn sfa
 where sfa.sicp_id(+)   = ux.sicid
   and sfa.risk_date(+) = ux.regdate
 order by 1, 6
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
