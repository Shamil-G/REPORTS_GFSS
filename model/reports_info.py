from flask import session,redirect, url_for
from util.logger import log
from model.list_reports import dict_reports


def get_owner_reports():
    # По умолчанию 
    # for dep_name in dict_reports == for dep_name in dict_reports.keys()
    return [{"dep_name": dep_name} for dep_name in dict_reports]


def get_list_groups():
    if 'dep_name' in session:
        dep_name = session['dep_name']
        dep_reps = dict_reports.get(dep_name)
        log.debug(f'GET LIST GROUPS. dep_reps: {dep_reps}')
        if dep_reps:
            list_grp = list(dep_reps.keys())

            log.debug(f'\n------> GET LIST REPORTS. List groups: {list_grp}')
            return list_grp
    return redirect(url_for('view_root'))


def get_list_reports():
    if 'dep_name' not in session or 'grp_name' not in session:
        return redirect(url_for('view_root'))
        
    group = dict_reports[session['dep_name']][session['grp_name']]
    
    return [
        {
            "num": num_rep,
            "name": rep["name"],
            "params": rep.get("params", {}),
            "meta_params": rep.get("meta_params", {})
        }
        for num_rep, rep in group["reports"].items()
    ]
