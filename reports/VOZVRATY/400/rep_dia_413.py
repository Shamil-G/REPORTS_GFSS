# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты для программы по возвратам», отчёт 413
(процедура REP_REPAY_413).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Возвраты (сравнение периодов) по предприятиям, обратившимся за возвратом три
и более раза: платёжные поручения ГФСС о возврате (`gfss_pay_doc`, состояния
3, 6, 7, 10) -> заявки (`mhmh_gfss_gcvp`, `sior_order_ret_gfss`) -> списки на
возврат (`gfss_order_ret_list`). Две таблицы подряд:
  1. «Информация по возвратам с <д1> по <д2>» - предприятия, у которых за
     период больше двух заявок (`count(distinct sior_id) > 2`);
  2. «... с <д3> по <д4> (из списка первого периода)» - предприятия, что
     обращались и во втором периоде и значатся в первом по условию из
     оригинала.
Внутри таблицы - по областям с подитогом «Всего», в конце - «Общий итог».
Колонки: область, район, предприятие, БИН, сумма возврата, число заявок, число
уникальных людей и по одной колонке на каждый вид ошибки (`vid_err` 1-13,
название из `repay_err_typ`); колонка вида ошибки выводится, только если по ней
есть данные в отчёте (как `z_colN <> 0` оригинала).

Формат. В приложении отчёт - одна таблица на листе, поэтому обе таблицы
сведены в одну: названия таблиц - жирные строки-разделители, колонки ошибок -
объединение по обеим таблицам.

Область и район предприятия - по справочнику организаций, как во всех живых
отчётах: `rfon_organization.bin = p_rnn` -> `cato_branch` по КАТО -> отделение
(`branch`): область - `branch.name` кода `<2 знака>00`, район -
`branch.short_name`. Нет в справочнике - «Неизвестный регион». Оригинал брал
их функциями `Regionname_po_rnn_2/_4` через устаревшую `rfrr_id_region`.

Особенности оригинала, сохранённые как есть:
  - во втором списке условие «три и более заявок» проверяется в подзапросе,
    который группирует ещё и по платёжному поручению (`pd2.mhmh_id`), то есть
    по заявкам одного поручения, а не предприятия целиком - как в `z_colN`;
  - «Всего» и «Общий итог» оригинал печатал со сдвигом на одну колонку
    (пропущена пустая ячейка перед суммой): здесь значения стоят под своими
    колонками;
  - счётчики заявок и людей в итогах оригинал форматировал денежной маской
    (две десятичные); здесь целые.

Параметры: два периода по дате платёжного поручения (с-по, с-по); конечные
даты включаются. Нижняя граница `between` заменена на `>= ... <`.

Таблицы gfss_*, mhmh_gfss_gcvp, sior_order_ret_gfss в reports_test недоступны:
запросы проверены на данных боевой БД (только чтение).
"""
import datetime
import os
import threading

from db.connect import LOADER_PROFILE, select_2
from model.manage_reports import set_status_report
from util.logger import log
from util.xlsx_report import build_report, Col, Group, parse_date, STATUS_ERROR

report_code = '413'
N_ERR = 13

_ERR_SUMS = ',\n'.join(
    f"       count(distinct decode(dl.vid_err, {k}, dl.sicid, null)) cnt{k}"
    for k in range(1, N_ERR + 1))

_BASE = """
  from gfss_pay_doc pd, mhmh_gfss_gcvp mh, sior_order_ret_gfss s,
       gfss_order_ret_list dl
 where pd.pay_date >= :d_from and pd.pay_date < :d_to
   and pd.state in (3, 6, 7, 10)
   and pd.mhmh_id = mh.mhmh_id
   and mh.sior_id = s.sior_id
   and pd.mhmh_id = dl.mhmh_id
   and s.sior_id = dl.sior_id"""

# предприятия периода, по которым больше двух заявок
_ROWS_1 = f"""
select s.p_rnn, s.p_name, sum(dl.sum_gfss) pay_sum,
       count(distinct mh.sior_id) cnt_zayav, count(distinct dl.sicid) cnt_chel,
{_ERR_SUMS}
{_BASE}
 group by s.p_rnn, s.p_name
having count(distinct mh.sior_id) > 2
"""

# какие колонки ошибок показывать (по документам с >2 заявок, как z_colN)
_ZCOLS_1 = f"""
select {', '.join(f'nvl(sum(xx.cnt{k}), 0) z{k}' for k in range(1, N_ERR + 1))}
  from (select count(distinct mh.sior_id) cnt_zayav,
{_ERR_SUMS}
{_BASE}
         group by pd.mhmh_id, s.p_rnn) xx
 where xx.cnt_zayav > 2
"""

_ROWS_2 = f"""
select s.p_rnn, s.p_name, sum(dl.sum_gfss) pay_sum,
       count(distinct mh.sior_id) cnt_zayav, count(distinct dl.sicid) cnt_chel,
{_ERR_SUMS}
{_BASE.replace(':d_from', ':d_from2').replace(':d_to', ':d_to2')}
   and exists (select 1
                 from (select count(distinct mh2.sior_id) cnt_zayav, s2.p_rnn
                         from gfss_pay_doc pd2, mhmh_gfss_gcvp mh2,
                              sior_order_ret_gfss s2, gfss_order_ret_list dl2
                        where pd2.pay_date >= :d_from and pd2.pay_date < :d_to
                          and pd2.state in (3, 6, 7, 10)
                          and pd2.mhmh_id = mh2.mhmh_id
                          and mh2.sior_id = s2.sior_id
                          and pd2.mhmh_id = dl2.mhmh_id
                          and s2.sior_id = dl2.sior_id
                        group by pd2.mhmh_id, s2.p_rnn) ss2
                where ss2.cnt_zayav > 2 and ss2.p_rnn = s.p_rnn)
 group by s.p_rnn, s.p_name
"""

_ZCOLS_2 = f"""
select {', '.join(f'nvl(sum(xx.cnt{k}), 0) z{k}' for k in range(1, N_ERR + 1))}
  from (select count(distinct mh.sior_id) cnt_zayav,
{_ERR_SUMS}
{_BASE.replace(':d_from', ':d_from2').replace(':d_to', ':d_to2')}
   and exists (select 1
                 from (select count(distinct mh1.sior_id) cnt_zayav, s1.p_rnn
                         from gfss_pay_doc pd1, mhmh_gfss_gcvp mh1,
                              sior_order_ret_gfss s1, gfss_order_ret_list dl1
                        where pd1.pay_date >= :d_from and pd1.pay_date < :d_to
                          and pd1.state in (3, 6, 7, 10)
                          and pd1.mhmh_id = mh1.mhmh_id
                          and mh1.sior_id = s1.sior_id
                          and pd1.mhmh_id = dl1.mhmh_id
                          and s1.sior_id = dl1.sior_id
                        group by pd1.mhmh_id, s1.p_rnn) ss
                where ss.cnt_zayav > 2 and ss.p_rnn = s.p_rnn)
         group by pd.mhmh_id, s.p_rnn) xx
 where xx.cnt_zayav > 2
"""

_REGION = """
select o.bin,
       max(nvl(br.name, 'Неизвестный регион')) obl,
       max(nvl(bd.short_name, 'Неизвестный регион')) raion
  from rfon_organization o, cato_branch cb, branch bd, branch br
 where o.bin in ({bins})
   and cb.code = o.cato
   and bd.rfbn_id(+) = cb.rfbn_id
   and br.rfbn_id(+) = substr(cb.rfbn_id, 1, 2) || '00'
 group by o.bin
"""


def _rows(sql, binds):
    return select_2(sql, binds, profile=LOADER_PROFILE, raise_on_error=True)


def _regions(bins):
    out = {}
    bins = sorted({str(b).strip() for b in bins if b})
    for i in range(0, len(bins), 500):
        chunk = bins[i:i + 500]
        names = {f'b{j}': b for j, b in enumerate(chunk)}
        sql = _REGION.format(bins=', '.join(f':{k}' for k in names))
        for r in _rows(sql, names):
            out[str(r['bin']).strip()] = (r['obl'], r['raion'])
    return out


def _err_names():
    names = {r['id']: f"{r['id']} - {r['name']}" for r in _rows(
        'select id, name from repay_err_typ', {})}
    return {k: names.get(k, f'{k}') for k in range(1, N_ERR + 1)}


def _compute(params):
    d1, d2 = parse_date(params['date_first']), parse_date(params['date_second'])
    d3, d4 = parse_date(params['date_third']), parse_date(params['date_fourth'])
    if d2 < d1 or d4 < d3:
        raise ValueError('Начальная дата больше конечной')
    one = datetime.timedelta(days=1)
    b1 = {'d_from': d1, 'd_to': d2 + one}
    b2 = {**b1, 'd_from2': d3, 'd_to2': d4 + one}
    rows1 = _rows(_ROWS_1, b1)
    z1 = _rows(_ZCOLS_1, b1)[0]
    rows2 = _rows(_ROWS_2, b2)
    z2 = _rows(_ZCOLS_2, b2)[0]
    regs = _regions([r['p_rnn'] for r in rows1 + rows2])
    show = [k for k in range(1, N_ERR + 1)
            if (z1.get(f'z{k}') or 0) != 0 or (z2.get(f'z{k}') or 0) != 0]
    return (d1, d2, d3, d4), rows1, rows2, regs, show


def _part(title, rows, regs, show):
    recs = [{'n': '', 'obl': title, 'bold': 1}]
    prepared = []
    for r in rows:
        obl, raion = regs.get(str(r['p_rnn']).strip(), ('Неизвестный регион', 'Неизвестный регион'))
        prepared.append((obl, r['p_name'] or '', raion, r))
    prepared.sort(key=lambda t: (t[0], t[1]))

    def blank():
        return {'pay_sum': 0, 'cnt_zayav': 0, 'cnt_chel': 0, **{f'err_{k}': 0 for k in range(1, N_ERR + 1)}}

    def add(acc, r):
        acc['pay_sum'] += r['pay_sum'] or 0
        acc['cnt_zayav'] += r['cnt_zayav'] or 0
        acc['cnt_chel'] += r['cnt_chel'] or 0
        for k in range(1, N_ERR + 1):
            acc[f'err_{k}'] += r[f'cnt{k}'] or 0

    def total_row(label, acc):
        return {'n': '', 'obl': label, 'bold': 1, **acc}

    obl_acc, all_acc, cur, n = blank(), blank(), None, 0
    for obl, _, raion, r in prepared:
        if cur is not None and obl != cur:
            recs.append(total_row('Всего', obl_acc))
            obl_acc = blank()
        cur = obl
        add(obl_acc, r)
        add(all_acc, r)
        n += 1
        rec = {'n': str(n), 'obl': obl, 'raion': raion, 'p_name': r['p_name'],
               'p_rnn': str(r['p_rnn']).strip(), 'pay_sum': r['pay_sum'],
               'cnt_zayav': r['cnt_zayav'], 'cnt_chel': r['cnt_chel']}
        for k in range(1, N_ERR + 1):
            rec[f'err_{k}'] = r[f'cnt{k}']
        recs.append(rec)
    if prepared:
        recs.append(total_row('Всего', obl_acc))
        recs.append(total_row('Общий итог', all_acc))
    return recs


def do_report(file_name, **params):
    if os.path.isfile(file_name):
        return file_name
    try:
        (d1, d2, d3, d4), rows1, rows2, regs, show = _compute(params)
        errs = _err_names()
    except Exception:
        log.exception(f'REPORT: {report_code}. Ошибка расчёта {file_name}')
        try:
            set_status_report(file_name, STATUS_ERROR)
        except Exception:
            log.exception('Не удалось выставить статус ошибки')
        raise
    columns = [Col('Область', 'obl', 'text', 28),
               Col('Район', 'raion', 'text', 28),
               Col('Наименование предприятия', 'p_name', 'text', 44),
               Col('БИН', 'p_rnn', 'center', 16),
               Col('Сумма', 'pay_sum', 'money', 18),
               Col('Кол. поступивших заявок', 'cnt_zayav', 'int', 14),
               Col('Кол. ун. чел. в списке на возврат', 'cnt_chel', 'int', 16)]
    if show:
        columns.append(Group('Виды ошибок', [
            Col(errs[k], f'err_{k}', 'int', 14) for k in show]))
    records = (_part(f'Информация по возвратам с {d1:%d.%m.%Y} по {d2:%d.%m.%Y}',
                     rows1, regs, show)
               + _part(f'Информация по возвратам с {d3:%d.%m.%Y} по {d4:%d.%m.%Y} '
                       f'(из списка первого периода)', rows2, regs, show))
    name = ('Отчет о возвратах (сравнение периодов) по предприятиям '
            '(3 и более раз)')
    inner, _ = build_report(
        code=report_code, name=name, columns=columns,
        stmt='-- расчёт в Python (rep_dia_413.py)', profile=LOADER_PROFILE,
        num_key='n', bold_key='bold', sheet_name='Возвраты',
        records_fn=lambda p: records)
    return inner(file_name, **params)


def thread_report(file_name, **params):
    log.info(f'THREAD REPORT. {report_code} -> {file_name}, params: {params}')
    threading.Thread(target=do_report, args=(file_name,), kwargs=params,
                     daemon=True).start()
    return {"status": 1, "file_path": file_name}
