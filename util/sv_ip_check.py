# -*- coding: utf-8 -*-
"""Общая сборка отчётов «Проверка СВ по БИН (ИИН ИП)»: AIS_GFSS 611
(процедура REP_R_3312, СВбр), 621-625 (REP_R_3312_1 ... REP_R_3312_5).

Пять процедур оригинала различаются только названием и видом выплаты
(`ss_m_pay.pc like '0701%'` ... `'0705%'`), поэтому запрос и колонки общие, а
модули отчётов `reports/DIA/600/rep_dia_611.py`, `rep_dia_621.py` ...
`rep_dia_625.py` только задают код, название и префикс вида выплаты.

Что делает отчёт. По БИН (или ИИН ИП) находит документы социальных отчислений
(`pmpd_pay_doc` + `pmdl_doc_list` + `em5_sird_reckon_donation`), по ним -
макеты решений о выплате указанного вида (`ss_m_pay` + `ss_m_sol`, поле
`sid` макета = `sipr_id` отчисления) и выводит получателей: регион, ИИН и
наименование ИП, ИИН и ФИО получателя, дату обращения, вид выплаты,
назначенную сумму, статус ЭМД.

Отличия от оригинала:
- `person.rn` заменён на `person.iin` (колонка переименована давно);
- наименование ИП - из `rfon_organization.nm_ru` по БИН (в оригинале
  `nk_minfin_iin`, справочник мёртв), нет записи - пусто;
- регион - название отделения из `branch.name` по коду `ss_m_sol.brid`
  (в оригинале `rfbn_branch.name`), правило Шамиля 14.10.2026;
- проверка `ss_m_pay.id = (select max(id) ... where id = mp.id)` оригинала
  всегда истинна (сравнивает ключ с самим собой) и опущена; подсказки
  оптимизатору (`parallel`, `leading`, `use_nl`, `index`) не переносятся;
- закомментированная в оригинале проверка «ИИН принадлежит ИП» не
  выполняется (так же, как в оригинале с 17.01.2020).

Таблицы `ss_m_pay`, `ss_m_sol`, `person`, `rfon_organization`, `branch`
reports_test видит; `em5_sird_reckon_donation` лежит в SSWH и недоступна,
поэтому запрос целиком на данных не сверен, только синтаксис.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col


def _check(params):
    if len(str(params.get('bin') or '').strip()) != 12:
        raise ValueError('Введен неправильный ИИН!')


COLUMNS = [
    Col('Код региона', 'brid', 'center', 10),
    Col('Регион', 'region', 'text', 30),
    Col('ИИН ИП', 'p_rnn', 'center', 16),
    Col('Наименование ИП', 'ip', 'text', 36),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО получателя', 'fio', 'text', 36),
    Col('Дата обращения', 'in_date', 'date', 14),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Назначенная сумма', 'ns', 'money', 16, total=False),
    Col('Статус ЭМД', 'st', 'center', 12),
]

# :bin - БИН или ИИН ИП (форма); {pc} - префикс вида выплаты.
_STMT = """
select distinct
       sp.brid,
       b.name region,
       rd.p_rnn,
       (select o.nm_ru from rfon_organization o
         where o.bin = rd.p_rnn and rownum = 1) ip,
       p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       sp.in_date,
       sp.pc,
       sp.ns,
       sp.st
  from (select mp.sid, ms.sicid, ms.brid, ms.in_date, ms.st, mp.pc,
               mp.nsum ns
          from ss_m_pay mp, ss_m_sol ms
         where ms.mpay = mp.id
           and mp.pc like '{pc}%') sp,
       (select sird.sipr_id, pd.p_rnn
          from em5_sird_reckon_donation sird, pmdl_doc_list dl,
               pmpd_pay_doc pd
         where pd.mhmh_id = sird.mhmh_id
           and pd.mhmh_id = dl.mhmh_id
           and sird.pmdl_n = dl.pmdl_n
           and pd.p_rnn = trim(:bin)) rd,
       person p,
       branch b
 where rd.sipr_id = sp.sid
   and p.sicid = sp.sicid
   and sp.brid = b.rfbn_id
 order by fio
"""


def make_report(code, name, pc):
    return build_report(
        code=code, name=name, columns=COLUMNS, stmt=_STMT.replace('{pc}', pc),
        profile=LOADER_PROFILE, check_params=_check,
    )
