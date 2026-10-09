-- Проверка таблиц под отчётами REPORTS_GFSS (боевая, под SSWH). Только чтение.
-- Список - 73 таблиц, на которые по коду ссылаются активные отчёты
-- model/list_reports.py (прямо или через представления, функции и процедуры SSWH;
-- раскрыто по слепку prod_dependencies 09.10.2026). Служебные load_tables_status и
-- log_load_tables не включены.
--
-- 1. Прямая задача: грузится ли каждая таблица и когда последний раз.
--    ls_*   - строка в load_tables_status (нет строки - пакеты загрузки о таблице не знают);
--    ldr_*  - одноимённый (или src_name) источник в LOADER: поток и последняя загрузка;
--    last_dml - последнее изменение по user_tab_modifications (пусто, если после него
--               собиралась статистика - тогда смотреть last_analyzed).
with t as
 (select column_value table_name
    from table(sys.odcivarchar2list(
    'AKTUAR_DEPENDANT', 'ALL_LIST_42500', 'BRANCH', 'CATO_BRANCH',
    'CTRL_MINSO', 'DIC_COUNTRY', 'EM5_SIRD_RECKON_DONATION', 'GFSS_ANNUL_PLAT',
    'GFSS_JOURNAL', 'GFSS_ORDER_RET_LIST', 'GFSS_PAY_DOC', 'GROUP_AGE2',
    'MHMH_GFSS_GCVP', 'MHMH_MSG_HEAD', 'MIN_SO_HISTORY', 'PAYMENT_HISTORY',
    'PERSON', 'PMDL_DOC_LIST', 'PMDL_DOC_LIST_S', 'PMPD_PAY_DOC',
    'PMPD_PAY_DOC_S', 'PNAP_ACT_PRT_2', 'PNDY_DAYPAY', 'PNPD_DOCUMENT',
    'PNPD_PAYMENT_DEPENDANT', 'PNPD_POTR', 'PNPT_PAYMENT', 'PREG_REGISTRY',
    'RFBL_BANK_LIST', 'RFBN_BRANCH_SITE', 'RFBS_BASE_SIZE', 'RFDS_DOC_STATUS',
    'RFDT_DOC_TYPE', 'RFON_ORGANIZATION', 'RFPF_PENSFUND', 'RFPM_PAYMENTS',
    'RFRC_RECIPIENT_ALL', 'RFRG_REGION', 'RFRR_ID_REGION', 'RFRR_REFERENCE',
    'RF_CONSTANTS', 'RIAC_ACTION', 'SERVICES_JOURN', 'SIAP_ACTION_PROTOCOL',
    'SIFL_FILE', 'SIFL_FILE_MAKET', 'SIHS_HISTORY', 'SIOR_ORDER_RET_ORIG',
    'SIPR_KSU', 'SIPR_MAKET_FIRST_APPROVE', 'SIPR_MAKET_FIRST_APPROVE_2', 'SIPR_PAYER',
    'SIPR_PAYER_ARC', 'SIPR_PAYER_MAKET', 'SI_MEMBER_2', 'SRDC_DEPENDANT_CATEGORY',
    'SRPM_PAYMENT', 'SS_DATA', 'SS_M_PAY', 'SS_M_SOL',
    'SS_M_SOL_ST', 'SS_Z_DOC', 'S_ERROR', 'S_INCOMINSIZE',
    'S_STATE', 'TEST_GFSS_ORDER_RET_LIST', 'TEST_GFSS_PAY_DOC', 'TEST_MHMH_GFSS_GCVP',
    'TEST_SIOR_ORDER_RET', 'UNEMPLOYED_CALC', 'VIRTUAL_DOC_LIST', 'V_LM_UNEMPLOY_SS_INFO',
    'WEB_GS_EMP')))
select t.table_name,
       ls.load_type ls_type, ls.group_num ls_group, ls.state ls_state,
       ls.last_success_date ls_success, ls.src_name,
       (select listagg(lt.period || decode(lt.is_remote, 'Y', ' (remote)'), ', ') within group(order by lt.period)
          from loader.load_table lt
         where upper(lt.dtable_name) = nvl(upper(ls.src_name), t.table_name)) ldr_stream,
       (select max(lst.end_time)
          from loader.load_tables_status lst
         where upper(lst.table_name) = nvl(upper(ls.src_name), t.table_name)) ldr_end,
       (select max(tm.timestamp) from user_tab_modifications tm where tm.table_name = t.table_name) last_dml,
       st.num_rows, st.last_analyzed
  from t, load_tables_status ls, user_tables st
 where ls.table_name(+) = t.table_name
   and st.table_name(+) = t.table_name
 order by ls.last_success_date nulls first, t.table_name;

-- 2. Обратная задача: строки load_tables_status, которые не нужны ни одному отчёту
--    REPORTS_GFSS - кандидаты на отключение загрузки.
with t as
 (select column_value table_name
    from table(sys.odcivarchar2list(
    'AKTUAR_DEPENDANT', 'ALL_LIST_42500', 'BRANCH', 'CATO_BRANCH',
    'CTRL_MINSO', 'DIC_COUNTRY', 'EM5_SIRD_RECKON_DONATION', 'GFSS_ANNUL_PLAT',
    'GFSS_JOURNAL', 'GFSS_ORDER_RET_LIST', 'GFSS_PAY_DOC', 'GROUP_AGE2',
    'MHMH_GFSS_GCVP', 'MHMH_MSG_HEAD', 'MIN_SO_HISTORY', 'PAYMENT_HISTORY',
    'PERSON', 'PMDL_DOC_LIST', 'PMDL_DOC_LIST_S', 'PMPD_PAY_DOC',
    'PMPD_PAY_DOC_S', 'PNAP_ACT_PRT_2', 'PNDY_DAYPAY', 'PNPD_DOCUMENT',
    'PNPD_PAYMENT_DEPENDANT', 'PNPD_POTR', 'PNPT_PAYMENT', 'PREG_REGISTRY',
    'RFBL_BANK_LIST', 'RFBN_BRANCH_SITE', 'RFBS_BASE_SIZE', 'RFDS_DOC_STATUS',
    'RFDT_DOC_TYPE', 'RFON_ORGANIZATION', 'RFPF_PENSFUND', 'RFPM_PAYMENTS',
    'RFRC_RECIPIENT_ALL', 'RFRG_REGION', 'RFRR_ID_REGION', 'RFRR_REFERENCE',
    'RF_CONSTANTS', 'RIAC_ACTION', 'SERVICES_JOURN', 'SIAP_ACTION_PROTOCOL',
    'SIFL_FILE', 'SIFL_FILE_MAKET', 'SIHS_HISTORY', 'SIOR_ORDER_RET_ORIG',
    'SIPR_KSU', 'SIPR_MAKET_FIRST_APPROVE', 'SIPR_MAKET_FIRST_APPROVE_2', 'SIPR_PAYER',
    'SIPR_PAYER_ARC', 'SIPR_PAYER_MAKET', 'SI_MEMBER_2', 'SRDC_DEPENDANT_CATEGORY',
    'SRPM_PAYMENT', 'SS_DATA', 'SS_M_PAY', 'SS_M_SOL',
    'SS_M_SOL_ST', 'SS_Z_DOC', 'S_ERROR', 'S_INCOMINSIZE',
    'S_STATE', 'TEST_GFSS_ORDER_RET_LIST', 'TEST_GFSS_PAY_DOC', 'TEST_MHMH_GFSS_GCVP',
    'TEST_SIOR_ORDER_RET', 'UNEMPLOYED_CALC', 'VIRTUAL_DOC_LIST', 'V_LM_UNEMPLOY_SS_INFO',
    'WEB_GS_EMP')))
select ls.table_name, ls.load_type, ls.group_num, ls.state, ls.last_success_date
  from load_tables_status ls
 where ls.table_name not in (select table_name from t)
 order by ls.table_name;
