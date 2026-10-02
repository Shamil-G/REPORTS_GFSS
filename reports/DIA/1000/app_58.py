# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 26. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_58_spool, Rep_app_58
# ============================================================
"""Приложение 58. Информация по оказанию услуг: назначения и отказы по
регионам и видам риска в разрезе канала обращения (ПЭП, ГК, ЦОН, ОЗиСП, МСЭ).

Перенос REP_STAT_EXTEND.app_58_spool + Rep_app_58 (pck_utf8.sql,
15431-15745 - расчёт; 15747-16161 - вывод). Протокол: 51 запуск (5 ошибок),
последний 04.09.2026, типы периода 1, 2, 4 (05.2019 - ещё 5).

Расчёт в оригинале - три независимых куска, здесь это три CTE:

1. `apr` - назначения (бывшая промежуточная `REP_58_a`): назначения из
   `sipr_maket_first_approve_2` за период, канал обращения - скалярным
   подзапросом `select unique name_source` по архиву макетов. Скалярный
   подзапрос сохранён намеренно: если у макета в архиве окажется два разных
   источника, Oracle упадёт с ORA-01427, как падал бы оригинал, а не
   размножит строку молча (п. 6 чек-листа).
2. `rcl` - пересмотр/перерасчёт (бывшая `REP_58_recalc_a`): действия
   `act_id = 102` в протоколе, кроме откатов.
3. `arc` + `rfs` - отказы: по всему архиву макетов окнами по `sipr_id`
   определяется дата первого утверждения, последний статус и был ли
   макет утверждён; отказ - не утверждён ни разу и последний статус
   3/5/8/11, дата первого утверждения - в периоде.

Колонки по каналу (col4..col10) - дословно как в оригинале: col5 ("через
ГК") = всего минус ПЭП, то есть туда же попадают макеты без источника;
col8 ("на альтернативной основе") = ОЗиСП + МСЭ.

Строки - все регионы RFRG_REGION на все виды 07xx из rfpm_payments
(Prn_SP, строки 16112-16128), регион печатается только в первой строке
своей группы. Пропуск печатается нулём, не пустой ячейкой (PrnOneGoup:
`else Rep.td(0)`) - отсюда nvl(..., 0) и blank_zero=False.

Две формы вывода оригинала ('m' и 'f', параметр irepTp) различаются
только строкой названия: 'f' печатает шапку без него. Здесь название есть
всегда, поэтому это один модуль, а не два.

ВОСПРОИЗВЕДЕНО КАК В ОРИГИНАЛЕ, ХОТЯ ПОХОЖЕ НА ОШИБКУ (решение - ДАУС):
- Пересмотр/перерасчёт в оригинале - подзапрос внутри выборки назначений,
  поэтому он попадает в отчёт только у пары регион+вид, где за период было
  хоть одно назначение. У пары без назначений перерасчёт теряется и
  печатается 0. Здесь так же (`case when a.cnt_all is not null`); чтобы
  показывать все перерасчёты, достаточно убрать этот case.
- `upper(ap.notes) not like ...` не пропускает действия с пустым notes
  (NULL not like - не истина). Возможно, так и задумано; оставлено.
- В отказах одно и то же обращение с двумя каналами в архиве считается
  дважды: distinct идёт по (sicp_id, name_source, ...), а не по sipr_id.

ОТЛИЧИЯ ОТ ОРИГИНАЛА:
- Перерасчёты отбирались `ap.act_date between p_DatB and p_DatE`, где p_DatE
  - последний день периода в 00:00: действия последнего дня после полуночи
  терялись. Здесь `>= :d_from and < :d_to` - последний день целиком.
  Назначения и отказы в оригинале уже брались с trunc() - там расхождения нет.
- Подпись 9 месяцев в оригинале печатала номер периода -1 (обёртка
  app_58_4_9m передаёт date_spare = -1): "Информация по оказанию услуг  -1 9
  месяцев 2026 года". Здесь без -1.
- Отказы в оригинале считались окнами по ВСЕМУ архиву макетов. Здесь архив
  заранее сужен до макетов, у которых есть статус 3/5/8/11 с датой расчёта
  в периоде. Фильтр по ключу партиции оставляет каждую партицию целиком,
  поэтому окна дают те же значения, а у макета, прошедшего фильтр
  `date_first_approve` в периоде, такая строка есть обязательно.
- Спул не удалял прежний расчёт перед вставкой, и повторный запуск за тот же
  период падал на XU_RPTB_REP_STAT_EXTEND_DATA (все 5 ошибок в протоколе -
  ORA-00001). Здесь EAV нет, вопрос снят.
- В спуле отказы писались с date_spare, оставшимся от последней строки
  назначений; если назначений за период не было, отказы уходили с NULL и
  месячная форма их не находила. Здесь такой зависимости нет.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.58'
# cSPTitle || PH_per (строки 15755, 16056).
report_name = 'Информация по оказанию услуг {period}'

# Begin блок Rep_app_58 (строки 16131-16154): месяц - v_rep_list_month.cap
# и год через пробел (единый шаблон «{Month} {year} года»), у остальных типов
# ведущий пробел дословно.
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: ' {year} год ',
})


def _channels(prefix):
    """Разбивка по каналу обращения - одинаковая у назначений и отказов."""
    return Group('В том числе', [
        Col('оказано через ПЭП', f'{prefix}4', 'int', 11),
        Col('оказано через ГК', f'{prefix}5', 'int', 11),
        Group('В том числе', [
            Col('дирекция ГК', f'{prefix}6', 'int', 11),
            Col('ЦОН', f'{prefix}7', 'int', 11),
            Col('оказано на альтернативной основе', f'{prefix}8', 'int', 13),
            Group('В том числе', [
                Col('ОЗиСП', f'{prefix}9', 'int', 11),
                Col('МСЭ', f'{prefix}10', 'int', 11),
            ]),
        ]),
    ])


# p_PageHead (строки 16003-16039).
COLUMNS = [
    Col('Регион', 'reg', 'text', 24),
    Col('Вид риска', 'rfpm_name', 'text', 30),
    Group('Назначенные', [
        Col('Пересмотр/\nперерасчет', 'cnt_recalc', 'int', 12),
        Col('всего', 'cnt_all', 'int', 11),
        _channels('a'),
    ]),
    Group('Отказы', [
        Col('всего', 'ref_all', 'int', 11),
        _channels('r'),
    ]),
]


def _by_channel(what):
    """Счётчики по каналам: имена источников дословно из srss_source.

    what - что считать: sicp_id у назначений (count(sicp_id) в REP_58_a),
    1 у отказов (там sum(case ... then 1 end)).
    """
    return f"""
           count({what}) cnt_all,
           count(case when name_source = 'ПЭП'          then {what} end) cnt_4,
           count(case when name_source = 'Отделение ГК' then {what} end) cnt_6,
           count(case when name_source = 'ЦОН'          then {what} end) cnt_7,
           count(case when name_source = 'ОЗиСП'        then {what} end) cnt_9,
           count(case when name_source = 'МСЭ'          then {what} end) cnt_10"""


def _out(alias, prefix):
    """col4..col10 из счётчиков: col5 = всего - ПЭП, col8 = ОЗиСП + МСЭ."""
    a = alias
    return f"""
       nvl({a}.cnt_4, 0)                       {prefix}4,
       nvl({a}.cnt_all, 0) - nvl({a}.cnt_4, 0) {prefix}5,
       nvl({a}.cnt_6, 0)                       {prefix}6,
       nvl({a}.cnt_7, 0)                       {prefix}7,
       nvl({a}.cnt_9, 0) + nvl({a}.cnt_10, 0)  {prefix}8,
       nvl({a}.cnt_9, 0)                       {prefix}9,
       nvl({a}.cnt_10, 0)                      {prefix}10"""


# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
STMT = f"""
with apr as (
    -- назначения за период (REP_58_a)
    select substr(ss.rfbn_id, 1, 2) obl,
           substr(ss.rfpm_id, 1, 4) rfpm,
           ss.sicp_id,
           (select unique sr.name_source
              from sipr_payer_maket_arc sp, srss_source sr
             where sp.sipr_id = ss.sipr_id
               and sp.source_type = sr.id_source) name_source
      from sipr_maket_first_approve_2 ss
     where ss.date_approve >= :d_from
       and ss.date_approve <  :d_to
),
apr_agg as (
    select obl, rfpm,{_by_channel('sicp_id')}
      from apr
     group by obl, rfpm
),
rcl as (
    -- пересмотр/перерасчёт (REP_58_recalc_a)
    select substr(sp.rfbn_id, 1, 2) obl,
           substr(sp.rfpm_id, 1, 4) rfpm,
           count(sp.sipr_id) cnt_recalc
      from siap_action_protocol ap, sipr_payer_maket_arc sp
     where ap.act_date >= :d_from
       and ap.act_date <  :d_to
       and ap.act_id = 102
       and ap.actp_id = sp.actp_id
       and upper(ap.notes) not like upper('%откат%')
     group by substr(sp.rfbn_id, 1, 2), substr(sp.rfpm_id, 1, 4)
),
arc as (
    -- история макета целиком: окна по sipr_id, как в оригинале
    select distinct ma.sicp_id, sn.name_source,
           first_value(substr(ma.rfbn_id, 1, 2))
               over (partition by ma.sipr_id order by ma.actp_id) obl,
           first_value(substr(ma.rfpm_id, 1, 4))
               over (partition by ma.sipr_id order by ma.actp_id) rfpm,
           count(distinct case when ma.state = 3 and rfcr_id is null then 1 end)
               over (partition by ma.sipr_id) is_appoint,
           min(case when ma.state in (3, 5, 8, 11) then ap.date_calc end)
               over (partition by ma.sipr_id) date_first_approve,
           first_value(ma.state)
               over (partition by ma.sipr_id order by ma.actp_id desc) last_state,
           first_value(ap.date_calc)
               over (partition by ma.sipr_id order by ma.actp_id) date_enter,
           max(case when ma.state = 2 and rfcr_id is null then ap.date_calc end)
               over (partition by ma.sipr_id) date_send_gfss,
           max(case when ma.state = 3 and rfcr_id is null then ap.date_calc end)
               over (partition by ma.sipr_id) date_last_approve
      from sipr_payer_maket_arc ma, siap_action_protocol ap, srss_source sn
     where ma.actp_id = ap.actp_id
       and ma.source_type = sn.id_source
       -- сужение по ключу партиции: макеты, утверждавшиеся в периоде
       and ma.sipr_id in (
               select ma2.sipr_id
                 from sipr_payer_maket_arc ma2, siap_action_protocol ap2
                where ma2.actp_id = ap2.actp_id
                  and ma2.state in (3, 5, 8, 11)
                  and ap2.date_calc >= :d_from
                  and ap2.date_calc <  :d_to)
),
rfs as (
    -- отказы: ни разу не утверждён, последний статус 3/5/8/11
    select obl, rfpm,{_by_channel('1')}
      from arc
     where date_first_approve >= :d_from
       and date_first_approve <  :d_to
       and is_appoint = 0
       and last_state in (3, 5, 8, 11)
     group by obl, rfpm
),
spine as (
    select rr.rfrg_id, rr.name reg_name, p.rfpm_id, p.name rfpm_name
      from RFRG_REGION rr, rfpm_payments p
     where substr(p.rfpm_id, 1, 2) = '07'
       and length(p.rfpm_id) = 4
)
select case when row_number() over (partition by s.rfrg_id
                                    order by s.rfpm_id) = 1
            then s.reg_name end reg,
       s.rfpm_name,
       -- перерасчёт виден только при назначениях (см. docstring)
       case when a.cnt_all is not null then nvl(c.cnt_recalc, 0) else 0 end cnt_recalc,
       nvl(a.cnt_all, 0) cnt_all,{_out('a', 'a')},
       nvl(f.cnt_all, 0) ref_all,{_out('f', 'r')}
  from spine s, apr_agg a, rcl c, rfs f
 where a.obl(+)  = s.rfrg_id and a.rfpm(+) = s.rfpm_id
   and c.obl(+)  = s.rfrg_id and c.rfpm(+) = s.rfpm_id
   and f.obl(+)  = s.rfrg_id and f.rfpm(+) = s.rfpm_id
 order by s.rfrg_id, s.rfpm_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label,
)
