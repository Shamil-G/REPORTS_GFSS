from os import path
from flask import  session, flash, request, render_template, redirect, url_for, send_from_directory, g
from flask_login import  login_required
from werkzeug.utils import secure_filename

from gfss_parameter import platform
from app_config import REPORT_PATH, LOG_PATH, styles
from main_app import app, log
from model.reports_info import get_owner_reports, get_list_groups, get_list_reports
from model.auxiliary_task import load_minso_dia
from model.call_report import call_report, check_report
from model.reports import list_reports_by_day
from model.manage_reports import remove_report
from datetime import date
from util.get_i18n import get_i18n_value
from os import environ

# from model.manage_user import change_passwd


list_params = []

empty_response_save = """
<h2>Hello World</h2>
<p>Maybe Must be used POST method with JSON data</p>
"""

empty_call_response = """
<h2>Hello World</h2>
<p>Maybe Must be used POST method with JSON data: DEP, GROUP and CODE parameter</p>
"""

#@app.route('/', methods=['POST', 'GET'])
#def view_index():
#    return empty_response_save, 200, {'Content-Type': 'text/html;charset=utf-8'}


@app.context_processor
def utility_processor():
    if 'style' not in session:
        session['style']=styles[0]    
        log.debug(f'------- CP\n\tSET SESSION STYLE: {session['style']}\n------')
    log.debug(f"------ CP. \n\tSET SESSION STYLE: {session['style']}\n\t{get_i18n_value('APP_NAME')}")
    return dict(res_value=get_i18n_value)


@app.route('/')
@app.route('/home', methods=['POST', 'GET'])
@login_required
def view_root():
    # if not g or 'user' not in g or g.user.is_anonymous():
    #     log.info(f"VIEW ROOT. NOT LOGIN")
    #     return redirect(url_for('login_page'))
    owners = get_owner_reports()
    if 'username' in session:
        log.debug(f"VIEW_ROOT. USERNAME: {session['username']}")
    return render_template("index.html", owner_cursor=owners)


@app.route('/change-style')
def change_style():
    if 'style' in session:
        for style in styles:
            if style!=session['style']:
                session['style']=style
                break
    else: 
        session['style']=styles[0]
    # Получим предыдущую страницу, чтобы на неё вернуться
    current_page = request.referrer
    log.debug(f"Set style {session['style']}. Next page: {current_page}")
    if current_page is not None:
        return redirect(current_page)
    else:
        return redirect(url_for('view_root'))


@app.route('/dep/<string:dep_name>', methods=['GET','POST'])
@login_required
def view_set_dep(dep_name):
    log.debug(f'SET_DEP: {dep_name}')
    #if request.method == 'POST':
    session['dep_name'] = dep_name
    log.debug(f"SET_DEP. DEP_NAME: {session['dep_name']}")
    list_groups = get_list_groups()
    log.debug(f"SET_DEP. DEP_NAME: {session['dep_name']}, LIST_GROUPS: {list_groups}")
    return render_template("list_grps.html", cursor=list_groups)


@app.route('/list-reports/<grp>', methods=['POST', 'GET'])
@login_required
def view_set_grp_name(grp):
    session['grp_name'] = str(grp)
    log.debug(f'---> SET_GRP_NAME/<grp>\n\tGRP_NAME: {grp}')
    grps = get_list_reports()
    log.debug(f'---> SET_GRP_NAME\n\tGROUPS: {grps}')
    if request.method == 'GET':
        return render_template("list_reports.html", cursor=grps)


@app.route('/extract-params/<int:rep_number>', methods=['GET', 'POST'])
@login_required
def view_extract_params(rep_number):
    rep_num = str(rep_number).zfill(2)
    session['rep_code'] = rep_num
    log.debug(f'1. VIEW EXTRACT PARAMS: {rep_number}')
    for rep in get_list_reports():
        log.debug(f'2. VIEW EXTRACT PARAMS.REP: {rep}')
        if rep_num == rep.get('num'):
            if 'meta_params' in rep:
                meta_params = rep.get('meta_params')
            if 'params' in rep:
                params = rep.get('params')
            log.debug(f"3. VIEW EXTRACT PARAMS. PARAMS: {params}")
            session['rep_name'] = rep['name']
            if meta_params and len(meta_params)>0:
                session['params'] = meta_params
                return redirect(url_for('view_set_params'))
            if params and len(params)>0:
                session['params'] = params
                return redirect(url_for('view_set_params'))
    return redirect(url_for('view_root'))


@app.route('/set-params', methods=['GET', 'POST'])
@login_required
def view_set_params():
    new_params = {}
    if 'params' not in session:
        log.info(f"-------\n\tERROR. EDIT_PARAMS. PARAMS not FOUND\n-------")
        return redirect(url_for('view_root'))

    list_params = session['params']
    log.debug(f'\nSET_PARAMS\n\tLIST_PARAMS:\t{list_params}')
    if request.method == 'POST':
        #Вытащим значения параметров из формы в новый список
        for parm in list_params:
            p = request.form[parm]
            new_params[parm] = p
        log.debug(f"EDIT_PARAMS. new_params: {new_params}")
        #Если параметры вытащили, то вызовем отчет
        if new_params:
            rep_code = session['rep_code']
            for rep in get_list_reports():
                if rep_code == rep.get('num'):
                    report = rep
                    report['params'] = new_params
                    result = call_report(session['dep_name'], session['grp_name'], session['rep_code'], new_params)
                    log.debug(f"EDIT_PARAMS. RESULT: {result}, PARAMS: {new_params}, report: {report}")
                    if 'status' in result:
                        status = result['status']
                        # 0 - отчет начал готовится
                        # 1 - отчет уже готовится
                        # 2 - отчет уже готов
                        # Если отчет готов(status==2), то выслать его получателю
                        if status == 2:
                            if 'file_path' in result:
                                row_path = path.normpath(result['file_path'])
                                head_tail = path.split(row_path)
                                file_path = str(head_tail[0])
                                file_name = str(head_tail[1])
                                log.info(f"EDIT_PARAMS. SEND REPORT. FILE_PATH: {file_path}, FILE_NAME: {file_name}")
                                return send_from_directory(file_path, file_name)
            return redirect(url_for('view_set_grp_name', grp=session['grp_name']))
    return render_template("edit_params.html", params=list_params)


@app.route('/language/<string:lang>')
def set_language(lang):
    log.info(f"Set language. LANG: {lang}, предыдущий язык: {session['language']}")
    session['language'] = lang
    # Получим предыдущую страницу, чтобы на неё вернуться
    current_page = request.referrer
    log.info(f"Set LANGUAGE. {current_page}")
    if current_page is not None:
        return redirect(current_page)
    else:
        return redirect(url_for('view_root'))


@app.route('/running-reports', methods=['POST', 'GET'])
@login_required
def view_running_reports():
    if '_flashes' in session:
        session['_flashes'].clear()
    if 'request_date' not in session:
        session['request_date'] = date.today().strftime('%Y-%m-%d')
    if request.method == "POST":
        session['request_date'] = request.form['request_date']
    log.debug(f"RUNNING REPORTS. REQUEST DATE: {session['request_date']}")
    list_reports = list_reports_by_day(session['request_date'])
    log.debug(f'RUNNING REPORTS. LIST REPORTS: {list_reports}')
    return render_template("running_reports.html", list = list_reports, request_date=session['request_date'])


@app.route('/uploads/<path:full_path>')
def uploaded_file(full_path):
    if platform == 'unix' and not full_path.startswith('/'):
        full_path = f'/{full_path}'
    file_path, file_name = path.split(full_path)
    log.debug(f"UPLOADED_FILE. FULL_PATH: {full_path}\n\tFILE_PATH: {file_path}\n\tFLE_NAME: {file_name}")
    if full_path.startswith(REPORT_PATH):
        status = check_report(full_path)
        log.debug(f"UPLOADED_FILE. STATUS: {status} : {type(status)}, PATH: {file_path}, file_name: {file_name}, REPORT_PATH: {REPORT_PATH}")
        if status == 2:
            log.info(f"UPLOADED_FILE. PATH: {file_path}, FILE_NAME: {file_name}")
            return send_from_directory(file_path, file_name)
    else:
        log.info(f"UPLOADED_FILE. FULL_PATH: {full_path}\nsplit_path: {file_path}\nreprt_path: {REPORT_PATH}")
    return redirect(url_for('view_running_reports'))


@app.route('/remove-reports/<string:date_report>/<int:num_report>')
@login_required
def view_remove_report(date_report,num_report):
    if 'Admin' in g.user.roles:
        log.info(f"REMOVE REPORT. {session['username']}. DATE_REPORT: {date_report}, NUM_REPORT: {num_report}, ROLES: {g.user.roles}")
        remove_report(date_report, num_report)
    return redirect(url_for('view_running_reports'))


@app.route('/auxiliary-task-dia')
@login_required
def view_auxiliary_task_dia():
    mess = '' 
    if 'aux_info' in session:
        mess = session['aux_info']
        session.pop('aux_info')
    return render_template("auxiliary_task_dia.html", info=mess)


@app.route('/load_minso_dia', methods=['POST', 'GET'])
@login_required
def view_load_minso_dia():
    if request.method == "POST":
        log.info(f'request: {request}')
        uploaded_file = request.files['file']
        if uploaded_file.filename!='':
            secure_fname = secure_filename(uploaded_file.filename)
            file_name = path.join(LOG_PATH,secure_fname)
            uploaded_file.save(file_name)
            count, all_cnt, table_name, mess = load_minso_dia(file_name)
            session['aux_info'] = mess
            log.info(f"VIEW_LOAD_MINSO\n\tLOAD_FILE: {file_name}\n\tloaded: {count}/{all_cnt}\n\tMESS: {mess}")
            if count<all_cnt:
                log.info(f"VIEW_LOAD_MINSO. DOWNLOAD LOG with ERROR: {LOG_PATH}/load_{secure_fname}.log")
                return send_from_directory(LOG_PATH, f'load_{table_name}.log')                
    log.info(f"VIEW_LOAD_MINSO\n\tUSER: {g.user.full_name}\n\tROLE: {g.user.roles}")
    return redirect(url_for('view_auxiliary_task_dia'))
