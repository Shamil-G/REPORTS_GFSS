# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3325 (процедура REP_R_3325).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Макет по СВчп (выплата 0706) по работодателю (БИН): решения по макетам
работников, за кого организация платила последние 13 месяцев.

В оригинале список работников писался во временную таблицу
`sicid_0706_maket` (`insert` с датой запроса и БИНом, после отчёта -
`delete` и `commit`) и читался из неё. Приложение отчётов ничего не пишет
в БД, поэтому тот же отбор (`pmpd_pay_doc` + `pmdl_doc_list` по `p_rnn`,
от первого числа месяца 13 месяцев назад до вчерашнего дня) стоит в
подзапросе `org`.

Основной запрос: `ss_m_sol` (решения) + `ss_m_pay` (назначения) +
`ss_m_sol_st` (статусы) + `rfms_m_sol` (названия) + `person`; решения с
заявлением от 16.03.2020 (`ms.z_date >= 16.03.2020`) до текущего момента,
статусы 7, 12 и 20, вид выплаты 0706. «Название» - причина отказа
(`st.ret_txt`) для статуса 12, иначе название статуса. В оригинале дата
16.03.2020 была строкой, зависящей от формата даты сессии - здесь она
явная. Закомментированное `ms.nsum > 0` не переносится.

Проверка БИНа как в оригинале: ровно 12 знаков. Название дословно.
Заголовки колонок - из `SetPageHead`; опечатки оригинала исправлены:
латинская «C» в «Статус», «Дата назначания» -> «Дата назначения».

Таблицы `ss_m_pay`, `rfms_m_sol`, `pmdl_doc_list` в тестовой reports_test
недоступны: на данных отчёт не сверен.

ИИН: в оригинале `person.rn`, но в `person` сейчас колонка `iin` (подтверждено
Шамилем 02.10.2026), здесь `person.iin`. Оригинал с `rn` давно не выполняется
(запрос динамический, ошибка глоталась), поэтому отчёт мог не использоваться год-два:
стоит подтвердить, нужен ли он.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3325'
report_name = 'Макет по СВчп\n\nБИН: {bin}'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 12),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('ИИН', 'rn', 'center', 16),
    Col('ФИО', 'fio', 'text', 40),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата окончания', 'stopdate', 'date', 14),
    Col('Дата решения', 'd_resh', 'date', 14),
    Col('Сумма', 'nsum', 'money', 16),
    Col('Статус', 'st', 'center', 10),
    Col('Название', 'status_name', 'text', 40),
]


def _check(params):
    if len(str(params.get('bin') or '').strip()) != 12:
        raise ValueError('Введен неправильный БИН!')


STMT = """
with org as (
    select unique dl.sicid
      from pmpd_pay_doc pd, pmdl_doc_list dl
     where pd.p_rnn = trim(:bin)
       and pd.mhmh_id = dl.mhmh_id
       and pd.pay_date >= add_months(trunc(sysdate, 'MONTH'), -13)
       and pd.pay_date <  trunc(sysdate)
)
select ms.brid,
       mp.pc,
       p.iin rn,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename as fio,
       mp.d_naz,
       mp.stopdate,
       ms.d_resh,
       ms.nsum,
       ms.st,
       case when ms.st = 12 then st.ret_txt else rs.name end status_name
  from org, ss_m_sol ms, ss_m_pay mp, ss_m_sol_st st, rfms_m_sol rs, person p
 where ms.mpay = mp.id
   and ms.sicid = p.sicid
   and ms.z_date >= date '2020-03-16'
   and ms.z_date <  sysdate
   and st.s_st in (7, 12, 20)
   and st.s_st = ms.st
   and org.sicid = p.sicid
   and rs.id_state = ms.st
   and ms.id = st.sid
   and substr(mp.pc, 1, 4) = '0706'
 order by p.iin desc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('bin',),
)
