# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 7013 (процедура Rep_Actuar_1_new_7013).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Провизии АО «Государственный фонд социального страхования» по одному
получателю (по ИИН) на дату провизии - то же, что отчёт 701 «Провизии», но
по одному человеку. Для каждой группы выплат считаются число получателей и
сумма обязательств по годам:
  1. потеря кормильца (0701) - срок выплаты зависит от числа иждивенцев и их
     предельного возраста (`spr_max_period`), коэффициент числа иждивенцев
     (`spr_amount_dependant`), годовые коэффициенты роста выплат
     (`spr_social_payments`) и доходности инвестиций (`spr_investment_incom`);
  2. утрата трудоспособности (0702) - до пенсионного возраста (58 лет для
     женщин, 63 для мужчин) с учётом смертности (`spr_deathrate_population`);
  3. потеря работы (0703) - до даты окончания выплаты, без коэффициентов;
  4. уход за ребёнком (0705) - до даты окончания (или год от назначения) со
     смертностью.
Строки каждой группы: «Численность» и «Сумма»; колонки - потребность
отчётного месяца (индекс 0 оригинала), годы и «Итого провизии». В конце -
«Провизии по всем получателям».

Расчёт ведётся на Python (циклы по годам и датам окончаний иждивенцев
SQL-ом не выражаются) и повторяет алгоритм процедуры построчно, включая
особенности оригинала: `months_between` и `add_months` по правилам Oracle,
выход из цикла по иждивенцам при дате раньше начала года (как в оригинале),
пустой коэффициент числа иждивенцев даёт пустую сумму. Отчёт выводится
одной таблицей (годы - колонки, диапазон лет - по данным).

Параметры: дата провизии (месяц, необязательно, пусто - текущий) и ИИН.
`person.rn` заменён на `person.iin` (причина невалидности процедуры в боевой
БД - `ORA-00904`, решение Шамиля 15.10.2026). Отличия: название оригинала
«Провизии АО "Государственный фонд...» без закрывающей кавычки - добавлена;
если в группе только индекс 0 (нет ни одного года), оригинал падал на
`for i in iCnt.Next(0) .. iCnt.last`, здесь выводятся только «Численность» и
«Сумму» потребности. Подписи оригинала не переносятся.

Таблицы `payment_history`, `pnpd_document`, `person`, `spr_*` проверены
запуском на данных боевой БД (только чтение); в reports_test часть таблиц
недоступна.
"""
import calendar
import datetime
import threading

from db.connect import LOADER_PROFILE, select_2
from model.manage_reports import set_status_report
from util.logger import log
from util.xlsx_report import (build_report, Col, parse_date, STATUS_ERROR)

report_code = '7013'

_SECTIONS = [
    ('1. Провизии для получателей по потере кормильца', '0701'),
    ('2. Провизии для получателей по утрате трудоспособности', '0702'),
    ('3. Провизии для получателей по потере работы', '0703'),
    ('4. Провизии для получателей по уходу за ребенком', '0705'),
]


# --- функции Oracle -------------------------------------------------------
def _last_day(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _is_last(d):
    return d.day == calendar.monthrange(d.year, d.month)[1]


def add_months(d, n):
    """add_months Oracle: конец месяца остаётся концом месяца."""
    d = _d(d)
    m = d.year * 12 + d.month - 1 + int(n)
    y, mo = divmod(m, 12)
    mo += 1
    last = calendar.monthrange(y, mo)[1]
    if _is_last(d):
        return datetime.date(y, mo, last)
    return datetime.date(y, mo, min(d.day, last))


def months_between(d1, d2):
    d1, d2 = _d(d1), _d(d2)
    whole = (d1.year - d2.year) * 12 + d1.month - d2.month
    if d1.day == d2.day or (_is_last(d1) and _is_last(d2)):
        return float(whole)
    return whole + (d1.day - d2.day) / 31.0


def _d(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    return v


# --- арифметика с пустыми значениями (NULL Oracle) ---------------------
def _add(a, b):
    return None if a is None or b is None else a + b


class _Acc:
    """p_Cnt / p_Sum оригинала: по индексу (0 или год) число и сумма."""

    def __init__(self):
        self.cnt = {}
        self.sum = {}

    def add(self, idx, s):
        if idx in self.cnt:
            self.cnt[idx] += 1
            self.sum[idx] = _add(self.sum[idx], s)
        else:
            self.cnt[idx] = 1
            self.sum[idx] = s


def _rows(sql, binds):
    return select_2(sql, binds, profile=LOADER_PROFILE, raise_on_error=True)


_PAYMENTS = """
select pr.birthdate, pr.sex, h.pnpt_id, h.sum_pay sum_all, h.stopdate stop_date,
       h.appointdate
  from payment_history h, pnpd_document dt, person pr
 where h.act_month = :rep_month
   and dt.pncp_date = h.act_month
   and dt.source_id = h.pnpt_id
   and dt.ridt_id = 6
   and dt.status in (1, 2, 3, 5, 7)
   and dt.rfpm_id like :rfpm || '%'
   and dt.pncd_id = pr.sicid
   and pr.sicid = :sicid
"""


def _compute(params):
    prov = parse_date(params.get('prov_date')) if params.get('prov_date') else datetime.date.today()
    prov = prov.replace(day=1)
    rep_month = add_months(prov, -1)
    beg_year = prov.year
    iin = str(params.get('iin') or '').strip()
    if len(iin) != 12:
        raise ValueError('Неверно указан ИИН!')

    incom = {r['year']: r['ratio'] for r in _rows(
        'select year, ratio from spr_social_payments where year >= :y', {'y': beg_year})}
    invest = {r['year']: r['ratio'] for r in _rows(
        'select year, ratio from spr_investment_incom where year >= :y', {'y': beg_year})}
    death = {r['k']: r['deathrate'] for r in _rows(
        'select age || \'_\' || sex k, deathrate from spr_deathrate_population', {})}
    dep_coeff = {}
    for r in _rows('select minval, maxval, kki from spr_amount_dependant', {}):
        for k in range(int(r['minval']), int(r['maxval']) + 1):
            dep_coeff[k] = r['kki']

    found = _rows('select sicid from person where iin = :iin', {'iin': iin})
    if not found:
        raise ValueError('Неверный ИИН')
    sicid = found[0]['sicid']

    def ratio(table, year):
        return table.get(year, 0)

    def death_rate(age, sex):
        return death.get(f'{age}_{sex}', 0)

    def fetch(rfpm):
        return _rows(_PAYMENTS, {'rep_month': rep_month, 'rfpm': rfpm, 'sicid': sicid})

    def pens_age(i):
        return add_months(i['birthdate'], 12 * (58 + 5 * int(i['sex'])))

    total = _Acc()
    out = []          # (заголовок, Acc)

    # 1. потеря кормильца
    acc = _Acc()
    for i in fetch('0701'):
        act = 1.0
        dep_date = {}
        cnt_dep = 0
        for d in _rows("""
            select pr.birthdate, pr.sex, mp.max_period
              from pnpd_payment_dependant pd, person pr, spr_max_period mp
             where pd.pnpt_id = :p and pd.sicid = pr.sicid
               and pd.rfpt_id = mp.srdc_id(+)""", {'p': i['pnpt_id']}):
            mp_ = d['max_period']
            idx = add_months(d['birthdate'], 12 * (mp_ if mp_ is not None else 58 + 5 * int(d['sex'])))
            dep_date[idx] = dep_date.get(idx, 0) + 1
            cnt_dep += 1
        acc.add(0, i['sum_all'])
        pa = pens_age(i)
        for g in range(beg_year, pa.year + 1):
            act = act * (1 + ratio(incom, g)) / (1 + ratio(invest, g))
            cnt = cnt_dep
            lo = max(prov, datetime.date(g, 1, 1))
            hi = min(pa, datetime.date(g, 12, 31))
            cnt_mes = 0.0
            for p_date in sorted(dep_date):
                if p_date > hi:
                    cnt_mes = _ratio_add(cnt_mes, months_between(hi, lo), dep_coeff, cnt, cnt_dep)
                    break
                elif p_date < lo:
                    break
                else:
                    cnt_mes = _ratio_add(cnt_mes, months_between(p_date, lo), dep_coeff, cnt, cnt_dep)
                    cnt -= dep_date[p_date]
                    lo = p_date
            if cnt_mes == 0:
                break
            acc.add(g, None if cnt_mes is None else cnt_mes * i['sum_all'] * act)
    out.append((_SECTIONS[0][0], acc))
    _fold(total, acc)

    # 2. утрата трудоспособности
    acc = _Acc()
    for i in fetch('0702'):
        act = 1.0
        lo = prov
        acc.add(0, i['sum_all'])
        pa = pens_age(i)
        for g in range(beg_year, pa.year + 1):
            act = act * (1 - death_rate(g - i['birthdate'].year, int(i['sex']))) \
                * (1 + ratio(incom, g)) / (1 + ratio(invest, g))
            hi = min(pa, datetime.date(g, 12, 31))
            if hi > lo:
                acc.add(g, months_between(hi, lo) * i['sum_all'] * act)
            lo = hi + datetime.timedelta(days=1)
    out.append((_SECTIONS[1][0], acc))
    _fold(total, acc)

    # 3. потеря работы
    acc = _Acc()
    for i in fetch('0703'):
        acc.add(0, i['sum_all'])
        if i['stop_date'] is not None and _d(i['stop_date']) > prov:
            acc.add(beg_year, i['sum_all'] * months_between(i['stop_date'], prov))
    out.append((_SECTIONS[2][0], acc))
    _fold(total, acc)

    # 4. уход за ребёнком
    acc = _Acc()
    for i in fetch('0705'):
        stop = i['stop_date'] if i['stop_date'] is not None else add_months(i['appointdate'], 12)
        stop = _d(stop)
        act = 1.0
        lo = prov
        acc.add(0, i['sum_all'])
        for g in range(beg_year, stop.year + 1):
            act = act * (1 - death_rate(g - i['birthdate'].year, int(i['sex']))) \
                * (1 + ratio(incom, g)) / (1 + ratio(invest, g))
            hi = min(stop, datetime.date(g, 12, 31))
            if hi > lo:
                acc.add(g, months_between(hi, lo) * i['sum_all'] * act)
            lo = hi + datetime.timedelta(days=1)
    out.append((_SECTIONS[3][0], acc))
    _fold(total, acc)
    out.append(('Провизии по всем получателям', total))

    years = sorted({y for _, a in out for y in a.cnt if y > 0})
    year_range = list(range(years[0], years[-1] + 1)) if years else []
    return prov, iin, out, year_range


def _ratio_add(cnt_mes, months, dep_coeff, cnt, cnt_dep):
    """p_CntMes + months * DepCoeff(cnt) / DepCoeff(cnt_dep); пусто - NULL."""
    a, b = dep_coeff.get(cnt), dep_coeff.get(cnt_dep)
    if cnt_mes is None or a is None or b is None:
        return None
    return cnt_mes + months * a / b


def _fold(total, acc):
    """SumTotal оригинала: добавить группу в общий итог."""
    for i, c in acc.cnt.items():
        if i in total.cnt:
            total.cnt[i] += c
            total.sum[i] = _add(total.sum[i], acc.sum[i])
        else:
            total.cnt[i] = c
            total.sum[i] = acc.sum[i]


def _records(out, year_range):
    recs = []
    for n, (title, acc) in enumerate(out, start=1):
        if not acc.cnt:
            continue                     # DumpProv: пустая группа не выводится
        label = str(n) if n <= len(_SECTIONS) else 'Итого'
        recs.append({'n': label, 'label': title, 'bold': 1})
        cnt_row = {'n': '', 'label': 'Численность', 'all': acc.cnt.get(0)}
        sum_row = {'n': '', 'label': 'Сумма', 'all': acc.sum.get(0)}
        tot = 0
        for y in year_range:
            cnt_row[f'y{y}'] = acc.cnt.get(y)
            sum_row[f'y{y}'] = acc.sum.get(y)
            tot = _add(tot, acc.sum.get(y)) if y in acc.sum else tot
        sum_row['total'] = tot if year_range else None
        recs += [cnt_row, sum_row]
    return recs


def do_report(file_name, **params):
    import os
    if os.path.isfile(file_name):
        return file_name
    try:
        prov, iin, out, year_range = _compute(params)
    except Exception:
        log.exception(f'REPORT: {report_code}. Ошибка расчёта {file_name}')
        try:
            set_status_report(file_name, STATUS_ERROR)
        except Exception:
            log.exception('Не удалось выставить статус ошибки')
        raise
    columns = [Col('Показатель', 'label', 'text', 36),
               Col('Потребность отчетного месяца', 'all', 'int', 18, total=False)]
    columns += [Col(f'{y} год', f'y{y}', 'int', 16, total=False) for y in year_range]
    columns.append(Col('Итого провизии', 'total', 'int', 18, total=False))
    name = (f'Провизии АО "Государственный фонд социального страхования"\n'
            f'по состоянию на {prov:%d.%m.%Y}\nИИН: {iin}')
    records = _records(out, year_range)
    inner, _ = build_report(
        code=report_code, name=name, columns=columns,
        stmt='-- расчёт в Python (rep_dia_7013.py)', profile=LOADER_PROFILE,
        num_key='n', bold_key='bold', sheet_name='Провизии',
        records_fn=lambda p: records)
    return inner(file_name, **params)


def thread_report(file_name, **params):
    log.info(f'THREAD REPORT. {report_code} -> {file_name}, params: {params}')
    threading.Thread(target=do_report, args=(file_name,), kwargs=params,
                     daemon=True).start()
    return {"status": 1, "file_path": file_name}
