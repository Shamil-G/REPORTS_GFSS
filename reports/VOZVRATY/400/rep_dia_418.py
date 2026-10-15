# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты для программы по возвратам», отчёт 418
(процедура REP_ORDER, «Распоряжение на возврат»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Приказ (ТАПСЫРЫС) на возврат излишне (ошибочно) уплаченных социальных
отчислений и пени на казахском языке и таблица сумм по КНП: файлы обмена с 1С
(`service_1c_exchange` + `service_1c_exchange_list`, `state = 0` - ещё не
обработанные), по каждому КНП всего (участников и сумма) и в том числе:
 - СО - записи с `mhmh_id` (платёж ГФСС), без типа;
 - ЕСП - записи без `mhmh_id` по КНП 026, без типа;
 - ЕП - записи типа 2 по КНП 026.
Участник = строка списка файла. Отчёт одностраничный документ: заголовок с
текстом приказа, таблица, подпись управляющего директора.

В оригинале этот отчёт есть только в веб-реестре (`WEB_S_REPS`, 418); в
настольном его нет. Параметр оригинала - код сотрудника, по нему печаталась
строка «орынд. <ФИО>» (`web_gs_emp`); здесь строки «орынд.» с пустым
исполнителем. Имя управляющего директора в подписи - как в активной части
оригинала (прежние варианты в нём закомментированы).

Текст приказа. В БД казахские буквы в этой строке утрачены (`?` - «ж?не»,
«Азаматтар?а», «арнал?ан» и т. д.); восстановлено по закомментированной
версии выше в том же коде и по смыслу: «Бухгалтерлік есеп және есептілік
департаменті «Азаматтарға арналған үкімет» Мемлекеттік корпорациясының шотына
келесі артық (қате) төленген әлеуметтік аударымдар мен (немесе) өсімпұлдар
сомаларын аударсын». Стоит сверить с оригиналом документа.

Таблицы проверены запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '418'
report_name = ('ТАПСЫРЫС\n'
               'Бухгалтерлік есеп және есептілік департаменті «Азаматтарға '
               'арналған үкімет» Мемлекеттік корпорациясының шотына келесі '
               'артық (қате) төленген әлеуметтік аударымдар мен (немесе) '
               'өсімпұлдар сомаларын аударсын:')

_P = 'Қатысушылар саны (адам)'
_S = 'Сома (теңге)'


def _pair(title, cnt, sm):
    return Group(title, [Col(_P, cnt, 'int', 14), Col(_S, sm, 'money', 18)])


COLUMNS = [
    Col('ТТК', 'knp', 'center', 8),
    _pair('Барлығы', 'cnt', 'sm'),
    Group('Оның ішінде', [
        _pair('СО', 'cnt026', 'sm026'),
        _pair('ЕСП', 'cntesp', 'smesp'),
        _pair('ЕП', 'cntep', 'smep'),
    ]),
]

STMT = """
select knp,
       count(1) cnt,
       sum(sum_gfss) sm,
       count(case when isesp = 1 and type is null then 1 end) cnt026,
       sum(case when isesp = 1 and type is null then sum_gfss else 0 end) sm026,
       count(case when isesp = 2 and knp = '026' and type is null then 1 end) cntesp,
       sum(case when isesp = 2 and knp = '026' and type is null then sum_gfss else 0 end) smesp,
       count(case when type = 2 and knp = '026' then 1 end) cntep,
       sum(case when type = 2 and knp = '026' then sum_gfss else 0 end) smep
  from (select s.knp, s.type, l.sum_gfss,
               case when s.mhmh_id is not null then 1 else 2 end isesp
          from service_1c_exchange s, service_1c_exchange_list l
         where s.id = l.file_id
           and s.state = 0)
 group by knp
 order by knp
"""

FOOTNOTE = ('«МӘСҚ» АҚ Басқарушы директор                              '
            'Б.Жунусов\n\nорынд. ____________________')

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, footnote=FOOTNOTE,
)
