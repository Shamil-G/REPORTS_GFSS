from  db.connect import get_connection, plsql_execute, select_one, plsql_proc_s
from  main_app import log
import os


stmt_file_path = f"""
    select st.file_path
    from LOAD_REPORT_STATUS st 
    where to_char(st.date_execute, 'YYYY-MM-DD') = :date_report
    and   st.num = :num_report
"""


def remove_file(date_report: str, num_report: int):
    params = {'date_report': date_report, 'num_report': num_report}
    result = select_one(stmt_file_path, params)
    if result and 'file_path' in result:
        file_path = result['file_path']
        if os.path.exists(file_path):
            log.info(f"REMOVE_FILE. NUM_REPORT: {num_report}, DATE_REPORT: {date_report}, FILE_PATH: {file_path}")
            os.remove(file_path)
        else:
            log.info(f"REMOVE_FILE. FILE NOT EXISTS: NUM_REPORT: {num_report}, DATE_REPORT: {date_report}, FILE_PATH: {file_path}")
        return True
    return False


def remove_report(date_report: str, num_report: int):
    if remove_file(date_report, num_report):
        log.info(f'REMOVE REPORT. NUM_REPORT: {num_report}, DATE_REPORT: {date_report}')
        plsql_proc_s('REMOVE REPORT. FILE NAME', 'reps.remove_report', [date_report, num_report])


def set_status_report(file_path: str, status: int):
    stmt_upd = f"""
      begin
          update LOAD_REPORT_STATUS st
          set st.status = :status,
              st.date_execute = sysdate
          where st.file_path = '{file_path}';
          commit;
      end;
    """
    log.info(f'SET STATUS REPORT. STATUS: {status}, FILE_PATH: {file_path}')
    with get_connection().cursor() as cursor:
        plsql_execute(cursor, 'SET STATUS REPORT', stmt_upd, [status])
