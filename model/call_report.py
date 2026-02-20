import importlib
from os import path, mkdir

from   db.connect import select_one, get_connection, plsql_execute
from   main_app import log
from   app_config import REPORT_PATH
from   gfss_parameter import platform
from   model.list_reports import dict_reports
from   model.manage_reports import remove_report
from   util.trunc_date import get_year



stmt_table = """
CREATE TABLE LOAD_REPORT_STATUS(
  date_execute DATE,
  num          number(3),
  code         varchar2(16),
  live_time    NUMBER(6,2),
  status       VARCHAR2(8),
  file_path    VARCHAR2(512)
)
tablespace DATA
  pctfree 10
  initrans 1
  maxtrans 255
  storage
  (
    initial 64K
    next 1M
    minextents 1
    maxextents unlimited
  );
"""

stmt_index = """
create unique index XU_LOAD_REPORT_STATUS_F_NAME on LOAD_REPORT_STATUS (file_path)
  tablespace DATA
  pctfree 10
  initrans 2
  maxtrans 255
  storage
  (
    initial 64K
    next 1M
    minextents 1
    maxextents unlimited
  );
"""
stmt_index_2 = """
create unique index XN_LOAD_REPORT_STATUS_DATE_EXECUTE_NUM on LOAD_REPORT_STATUS (DATE_EXECUTE, NUM)
  tablespace DATA
  pctfree 10
  initrans 2
  maxtrans 255
  storage
  (
    initial 64K
    next 1M
    minextents 1
    maxextents unlimited
  );
"""
        

def check_dir(dir_path: str):
    if not path.isdir(dir_path):
        mkdir(dir_path)
        
        

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
        

def check_report(file_path: str):
    stmt = f"""
      select to_char(st.date_execute,'YYYY-MM-DD') as date_report, 
             st.num num_report, 
             st.status, 
            case 
                when st.live_time = 0 then 1
                when st.status = 2 then
                    date_execute + 
                    (case when st.live_time>0 then st.live_time/24 else 1 end) -
                    (case when st.live_time>0 then sysdate else st.date_execute end) 
                when trunc(st.date_execute) != trunc(sysdate) and st.status = 1 then
                     0
                else st.live_time 
            end  as remain_time
      from LOAD_REPORT_STATUS st 
      where st.file_path = :file_path
    """
    result = select_one(stmt, {'file_path': file_path})
    if result:
        date_report = result['date_report']
        num_report = result['num_report']
        status = int(result['status'])
        remain_time = result['remain_time']
        log.debug(f"CHECK_REPORT. result: {result}, status: {status}, idate_report: {date_report}, inum_report: {num_report}")
        if remain_time <= 0:
            log.info(f"CHECK_REPORT. REMOVE. REMAIN TIME: {remain_time}, idate_report: {date_report}, inum_report: {num_report}")
            remove_report(date_report, num_report)
            status = 0
        return status
    return 10


def init_report(name_report: str, date_first: str, date_second: str, rfpm_id: str, rfbn_id: str, live_time: str, file_path: str):
    status = 0
    with get_connection() as conn:
        with conn.cursor() as cursor:
            status =cursor.callfunc('reps.add_report', int, [name_report, date_first, date_second, rfpm_id, rfbn_id, live_time, file_path])
    # 0 - файл отсутствует
    # 1 - Файл готовится
    # 2 - Файл готов
    # 10 - Журнал не содержит информаци об отчете
    return status


def call_report(dep_name: str, group_name: str, code: str, params: dict):
    log.info(f'\nCALL REPORT. DEP: {dep_name}, group: {group_name}, code: {code}, input_params: {params}')

    log.debug(f"--- PARAMS: {params}")
    #Определим владельца отчета-департамент
    if dep_name in dict_reports:
        dp = dict_reports[dep_name]
        log.debug(f'\n---> CALL REPORT. DP: {dp}')
        #Переберем все группы для выбора нужной по имени
        for cur_group in dp:
            if cur_group['grp_name'] == group_name:
                list_reports = cur_group['list']
                log.debug(f'\n-----> CALL REPORT. CUR_GROUP: {cur_group}')
                log.debug(f'\n-------> CALL REPORT. LIST_REPORTS: {list_reports}')
                for curr_report in list_reports:
                    #Определяем код отчета в группе
                    if code == curr_report['num_rep']:
                        # log.info(f'\n-------> CALL REPORT. CODE. DEP: {dep_name}, CODE: {code}, CUR_GROUP: {cur_group}, params: {params}')
                        #Определим по коду отчета имя Python модуля для последующей загрузке
                        if 'proc' in curr_report:
                            #  Параметры дат отчетов надо заложить в имя файла
                            #  Четыре параметра используются в init_report
                            date_first = ''
                            date_second = ''
                            rfpm_id = ''
                            rfbn_id = ''

                            if 'rfbn_id' in params:
                                rfbn_id = params['rfbn_id']
                            if 'rfpm_id' in params:
                                rfpm_id = params['rfpm_id']

                            if 'date_first' in params:
                                date_first = params['date_first']
                            if 'date_second' in params:
                                date_second = params['date_second']
                            #

                            check_dir(f'{REPORT_PATH}/{get_year(date_first)}')
                            report_part_path = f'{REPORT_PATH}/{get_year(date_first)}/{dep_name}.{group_name}.{code}'
                            proc = curr_report['proc']

                            log.debug(f'\n-------> CALL REPORT. PROC: {proc}')
                            #Определим время жизни отчета
                            live_time = 0
                            if 'live_time' in cur_group:
                                live_time = cur_group['live_time']

                            # Загрузим модуль отчетности
                            # 1. Определим путь для импорта необходимого Python модуля-отчета
                            module_dir = cur_group['module_dir']
                            module_path = f"{module_dir}.{proc}"
                            log.debug(f'CALL REPORT. MODULE DIR: {module_dir}, MODULE PATH: {module_path}')
                            # 2. Загрузим модуль по найденному пути
                            loaded_module = importlib.import_module(module_path)

                            # Найдем в модуле rep_code
                            if hasattr(loaded_module,'report_code'):
                                rep_code = getattr(loaded_module,'report_code')

                            # Найдем в модуле функцию формирования имени файла, если она есть
                            # 1. Проверяем модуль на наличе функции 'get_file_full_name'
                            # 2. Извлекаем имя с полным путем
                            if hasattr(loaded_module,'get_file_full_name'):
                                # file_name = loaded_module.get_file_path(**params)
                                get_file_name = getattr(loaded_module,'get_file_full_name')
                                file_name = get_file_name(report_part_path, params)
                                log.info(f'\nCALL REPORT. GET FILE FULL NAME. FILE_NAME {file_name}\nparams:{params}\n')
                            else:
                                report_part_path = f'{report_part_path}.{rep_code}'
                                prefix_path_name = ".".join([
                                    value for key, value in params.items()
                                    if value not in [None, "", [], {}]
                                ])
                                report_part_path = f'{report_part_path}.{prefix_path_name}'

                                file_name = f'{report_part_path}.xlsx'

                            log.debug(f'CALL_REPORT. PARAMS: {params}')

                            # Дополним параметром начального пути для отчета
                            params['file_name']=file_name

                            # log.info(f'CALL REPORT. GET FILE NAME. file_name: {file_name}')
                            status = int(check_report(file_name))
 
                            ##log.info(f'CALL REPORT. CHECK REPORT. status: {status}')
                            if status < 0:
                                log.info(f'CALL REPORT. Ошибка статуса. {status}. {file_name}')
                                return {"status": status}
                            # Если запись об отчете в БД присутствует
                            if status in (1, 2): # Файл готовится или готов
                                if status == 1:
                                    log.info(f'CALL REPORT. Отчет готовится. status: {status}. {file_name}')
                                if status == 2:
                                    log.info(f'CALL REPORT. Отчет готов. status: {status}. {file_name}')
                                return {"status": status, "file_path": file_name}

                            # Если запись об отчете в БД отсутствует, то ее надо сделать
                            if status in (0,10):
                                status = init_report(f'{group_name}.{code}.{rep_code}', date_first, date_second, rfpm_id, rfbn_id, live_time, file_name)
                                log.debug(f'CALL REPORT. Status: {status}')
                                if status == 1:
                                    log.info(f'CALL REPORT. REPORT PREPARING. Status: {status}, file_name: {file_name}')
                                    return {"status": status, "file_path": file_name}
                                if status == 2:
                                    log.info(f'CALL REPORT. RESULT EXIST. Status: {status}, file_name: {file_name}')
                                    return {"status": status, "file_path": file_name}
                                log.info(f'MAKE_REPORT. Start {module_path} -> {file_name}')

                                params['file_name']=file_name

                                # Получаем полный путь к файлу - результату
                                # log.info(f'CALL_REPORT. PARAMS: {params}')

                                if platform == 'unix':
                                    from os import fork
                                    pid = fork()
                                    if pid:
                                        return {"status": 1, "file_path": file_name}
                                    else:
                                        log.info(f'CALL REPORT. CHILD FORK PROCESS. {file_name}')
                                        loaded_module.do_report(**params)
                                else:
                                    log.info(f'CALL REPORT. THREAD PROCESS. \nBEG PARAMS ---------------------\n{params}\nEND PARAMS ---------------------')
                                    result = loaded_module.thread_report(**params)
                                    return result
    return {"status": 0, "file_path": "Mistake in parameters"}

