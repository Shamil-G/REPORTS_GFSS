from flask import session,redirect, url_for
from util.logger import log
from util import access
from model.list_reports import dict_reports, dict_access, DYNAMIC_VALUES, regions_values


def resolve_dynamic(meta_params: dict) -> dict:
    """Подставляет значения, зависящие от текущей даты.

    Описание параметра может нести ключ "dynamic" - карту "имя поля -> имя
    вычислителя из DYNAMIC_VALUES". Считать их при импорте нельзя: meta_params
    живёт в dict_reports всё время работы процесса и попадает в сессию
    пользователя, поэтому список годов застыл бы на дате старта приложения.
    Результат - обычные словари, они нормально сериализуются в сессию.
    """
    resolved = {}
    for key, val in meta_params.items():
        if isinstance(val, dict) and "dynamic" in val:
            val = {k: v for k, v in val.items() if k != "dynamic"}
            for field, name in meta_params[key]["dynamic"].items():
                val[field] = DYNAMIC_VALUES[name]()
        resolved[key] = val
    return resolved


def visible_group(group: dict, dep_name: str) -> bool:
    """Показывать ли группу: доступна она сама или хотя бы один её отчёт.

    Отчёт со своим ключом "access" может быть открыт шире группы - тогда
    группу надо показать, иначе до отчёта не добраться.
    """
    user = access.current_user()
    dep_rule = dict_access.get(dep_name)
    if access.allowed(user, access.effective_access(group, None, dep_rule)):
        return True
    return any(access.allowed(user, access.effective_access(group, rep, dep_rule))
               for rep in group.get("reports", {}).values())


def visible_report(group: dict, report: dict, dep_name: str) -> bool:
    return access.allowed(access.current_user(),
                          access.effective_access(group, report,
                                                  dict_access.get(dep_name)))


def own_region_param(meta_params: dict, group: dict, report: dict,
                     dep_name: str) -> dict:
    """Область в форме при access с "own": филиалу - своя, без выбора.

    Центральному аппарату список остаётся прежним (вся республика и любая
    область). Подмена значения в форме ничего не даёт: call_report всё равно
    ставит область сам, это только подпись для пользователя.
    """
    forced = access.forced_rfbn(access.current_user(),
                                access.effective_access(group, report,
                                                        dict_access.get(dep_name)))
    if not forced or "rfbn_id" not in meta_params:
        return meta_params
    region = dict(meta_params["rfbn_id"])
    region["values"] = {forced: regions_values.get(forced, forced)}
    region["default"] = forced
    region["required"] = True
    region.pop("empty_label", None)
    return {**meta_params, "rfbn_id": region}


def get_owner_reports():
    # По умолчанию
    # for dep_name in dict_reports == for dep_name in dict_reports.keys()
    # Отдел показывается, если в нём есть хоть одна доступная группа.
    return [{"dep_name": dep_name} for dep_name, groups in dict_reports.items()
            if any(visible_group(group, dep_name) for group in groups.values())]


def get_list_groups():
    if 'dep_name' in session:
        dep_name = session['dep_name']
        dep_reps = dict_reports.get(dep_name)
        log.debug(f'GET LIST GROUPS. dep_reps: {dep_reps}')
        if dep_reps:
            list_grp = [grp for grp, group in dep_reps.items()
                        if visible_group(group, dep_name)]

            log.debug(f'\n------> GET LIST REPORTS. List groups: {list_grp}')
            return list_grp
    return redirect(url_for('view_root'))


def get_list_reports():
    if 'dep_name' not in session or 'grp_name' not in session:
        return redirect(url_for('view_root'))

    dep_name = session['dep_name']
    group = dict_reports[dep_name][session['grp_name']]

    return [
        {
            "num": num_rep,
            "name": rep["name"],
            "params": rep.get("params", {}),
            "meta_params": own_region_param(
                resolve_dynamic(rep.get("meta_params", {})), group, rep, dep_name)
        }
        for num_rep, rep in group["reports"].items()
        if visible_report(group, rep, dep_name)
    ]
