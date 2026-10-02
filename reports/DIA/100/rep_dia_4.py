# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 4 (процедура rep_r_4).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Мониторинг движения макетов дел по виду выплаты на текущую дату: по
регионам число обратившихся и дел по этапам - подготовленные, отправленные
на утверждение в Департамент, отказы, утверждённые Департаментом, находящиеся
на выплате, с оконченными выплатами.

Параметр `rfpm_kind` - вид выплаты (в оригинале `par1`, цифра `1`-`6`): 1 - потеря кормильца
(0701), 2 - утрата трудоспособности (0702), 3 - потеря работы (0703),
4 - беременность и роды (0704), 5 - уход за ребёнком до 1 года (0705),
6 - усыновление новорождённого (код 07040301 без маски `%`, как в оригинале:
точное совпадение). Текст названия зависит от вида - дословно из `rep_var`
(грамматика «по потери» -> «по потере», лишние пробелы убраны).

Источник - макеты двух поколений (`union all`): `sipr_payer_maket` +
`sifl_file_maket` и `sipr_payer` + `sifl_file`; этапы - по `state`: 0, 1, 9, 4,
7, 8 - подготовлено; 2, 10 - отправлено; 5, 11 - отказы; 3 - утверждено; 12 -
на выплате; 13 - выплата окончена. «Обратившиеся» - все состояния. Итоговая
строка - `grouping sets (1, (reg, s_region_name(reg)))` с пустым регионом.

Дата в названии - дата формирования (`sysdate` в оригинале).
Заголовки - из `SetPageHead` (`<br>` заменены пробелами). Таблицы
`sipr_payer_maket`, `sifl_file_maket`, `sipr_payer`, `sifl_file` лежат в схеме SSWH
боевой БД, в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '4'
report_name = 'Мониторинг движения макетов дел {rfpm_kind} на {today} г.'

# rep_var оригинала (грамматика и пробелы исправлены)
TEXT_PARAMS = {'rfpm_kind': {
    '1': 'по потере кормильца',
    '2': 'по утрате трудоспособности',
    '3': 'по потере работы',
    '4': 'по потере дохода в связи с беременностью и родами',
    '5': 'по потере дохода по уходу до 1 года',
    '6': 'по потере дохода в связи с усыновлением (удочерением) новорожденного',
}}

COLUMNS = [
    Col('Код области', 'reg', 'center', 10),
    Col('Наименование области', 'regname', 'text', 36),
    Col('Кол-во обратившихся', 'all_cnt', 'int', 14),
    Col('Кол-во подготовленных макетов', 'cnt1', 'int', 16),
    Col('Кол-во отправленных на утверждение в Департамент', 'cnt2', 'int', 20),
    Col('Кол-во отказов', 'cnt3', 'int', 12),
    Col('Кол-во дел утвержденных Департаментом', 'cnt4', 'int', 18),
    Col('Общее количество дел на выплате', 'cnt5', 'int', 16),
    Col('Кол-во дел с оконченными выплатами', 'cnt6', 'int', 16),
]

# :rfpm_kind - вид выплаты (1-6), расшифровка маски - в decode.
STMT = """
select reg, s_region_name(reg) regname, sum(cnt) all_cnt,
       sum(case when state in (0, 1, 9, 4, 7, 8) then cnt else 0 end) cnt1,
       sum(case when state in (2, 10) then cnt else 0 end) cnt2,
       sum(case when state in (5, 11) then cnt else 0 end) cnt3,
       sum(case when state in (3) then cnt else 0 end) cnt4,
       sum(case when state in (12) then cnt else 0 end) cnt5,
       sum(case when state in (13) then cnt else 0 end) cnt6
  from (select substr(sfm.rfbn_id, 1, 2) reg, sfm.state, count(*) cnt
          from sipr_payer_maket sfm, sifl_file_maket ssm
         where sfm.sipr_id = ssm.sipr_id
           and sfm.rfpm_id like decode(:rfpm_kind, '6', '07040301', '5', '0705%',
                                       '1', '0701%', '3', '0703%', '4', '0704%',
                                       '2', '0702%')
         group by substr(sfm.rfbn_id, 1, 2), sfm.state
        union all
        select substr(sfm.rfbn_id, 1, 2) reg, sfm.state, count(*) cnt
          from sipr_payer sfm, sifl_file ssm
         where sfm.sipr_id = ssm.sipr_id
           and sfm.rfpm_id like decode(:rfpm_kind, '6', '07040301', '5', '0705%',
                                       '1', '0701%', '3', '0703%', '4', '0704%',
                                       '2', '0702%')
         group by substr(sfm.rfbn_id, 1, 2), sfm.state)
 group by grouping sets (1, (reg, s_region_name(reg)))
 order by 1
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, text_params=TEXT_PARAMS,
)
