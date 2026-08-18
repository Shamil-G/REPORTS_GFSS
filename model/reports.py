from util.logger import log
from db.connect import get_connection
from datetime import datetime
from model.manage_reports import set_status_report, remove_report
from util.trunc_date import first_day, last_day
import os

stmt_list_reports_month = """
    select  to_char(st.date_execute,'YYYY-MM-DD'), st.num, st.date_first, st.date_second, st.rfpm_id, 
            st.rfbn_id, st.name, st.live_time, st.status, st.file_path,
            case 
                when live_time = 0 then 72
                when st.status = 2 then
                    date_execute + 
                    (case when live_time>0 then live_time/24 else 1 end) -
                    (case when live_time>0 then sysdate else date_execute end) 
                when trunc(st.date_execute) != trunc(sysdate) and st.status = 1 then
                     0
                else live_time 
            end           
    from load_report_status st
    where trunc(st.date_execute,'MM') = trunc(to_date(:i_date,'YYYY-MM-DD'), 'MM')
    order by st.num
"""

stmt_list_reports = """
    select  to_char(st.date_execute,'YYYY-MM-DD'), st.num, st.date_first, st.date_second, st.rfpm_id, 
            st.rfbn_id, st.name, st.live_time, st.status, st.file_path,
            case 
                when live_time = 0 then 72
                when st.status = 2 then
                    date_execute + 
                    (case when live_time>0 then live_time/24 else 1 end) -
                    (case when live_time>0 then sysdate else date_execute end) 
                when trunc(st.date_execute) != trunc(sysdate) and st.status = 1 then
                     0
                else live_time 
            end           
    from load_report_status st
    where trunc(st.date_execute,'DD') = to_date(:i_date,'YYYY-MM-DD')
    order by st.num
"""

def list_reports_by_day(request_day):
    current_day = datetime.today().strftime('%Y-%m-%d')
    results = []
    stmt = ''
    log.info(f'LIST REPORTS BY DAY. request_day: {request_day}, current_day: {current_day}')
    with get_connection() as connection:
        with connection.cursor() as cursor:
            log.debug(f'LIST REPORTS BY DAY. CURSOR CREATED')
            if first_day(request_day) == request_day or last_day(request_day) == request_day:
                stmt = stmt_list_reports_month
            else:
                stmt = stmt_list_reports
            cursor.execute(stmt, i_date=request_day)
            log.debug(f'LIST REPORTS BY DAY. request_day: {request_day}\n--------\n{stmt}\n--------')
            rows = cursor.fetchall() 
            if rows:
                for row in rows:
                    remain_time = row[10]
                    date_execute = row[0]
                    file_exist = os.path.exists(row[9])
                    status = int(row[8])
                    if status!=2 and file_exist:
                        set_status_report(row[9],2)
                    if remain_time <= 0:
                        log.info(f"CHECK_REPORT. REMOVE. REMAIN TIME: {remain_time} <= 0, date_report: {request_day}, inum_report: {row[1]}")
                        remove_report(row[0], row[1])
                    elif not file_exist and status == 2:
                        log.info(f"CHECK_REPORT. REMOVE. FILE NOT EXISTS. num_report: {row[1]}, file: {row[9]}")
                        remove_report(row[0], row[1])
                    elif status == 1 and current_day != date_execute:
                        log.info(f"CHECK_REPORT. REMOVE. STATUS: {status}, date_execute: {date_execute}, current_day: {current_day}, file: {row[9]}")
                        remove_report(row[0], row[1])
                    else:
                        info = { "date_event": row[0], "num": row[1], "date_first": row[2], "date_second": row[3], 
                                 "rfpm_id": row[4], "rfbn_id": row[5], 
                                 "name": row[6], "live_time": row[7], "status": status, "path": row[9]}
                        results.append(info)
                        log.debug(f"LIST REPORTS BY DAY. status: {info['status']}, exist: {file_exist}, path: {info['path']}")
                rows.clear()
    return results
