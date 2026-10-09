-- Строки s_load_table для таблиц, которые грузятся своими пакетами LOAD_<таблица>.MAKE
-- (load_type в load_tables_status пуст): источник в LOADER -> приёмник SSWH.
-- По ним batch_upload_table определяет поток и свежесть источника.
-- period = 'L' - любое значение, кроме 'N' (отключено); 'L' - для наглядности.
-- ord: PMDL_DOC_LIST строится с участием SSWH.PMPD_PAY_DOC, поэтому грузится после неё.
-- Не добавлены: MIN_SO_HISTORY, SI_MEMBER_2, SIPR_MAKET_FIRST_APPROVE_2 - строятся из таблиц SSWH,
-- источника в LOADER у них нет; остаются на своих джобах.
-- Строка не добавляется, если приёмник в s_load_table уже есть.
Insert Into s_load_table
  (id, ord, period, ldr_name, dst_owner, dst_name)
  Select (Select Nvl(Max(id), 0) From s_load_table) + Rownum, n.ord, 'L', n.ldr_name, 'SSWH', n.dst_name
    From (Select 'EM5_SIRD_RECKON_DONATION' ldr_name, 'EM5_SIRD_RECKON_DONATION' dst_name, Null ord From dual Union All
          Select 'MHMH_MSG_HEAD',            'MHMH_MSG_HEAD',            Null From dual Union All
          Select 'PAYMENT_HISTORY',          'PAYMENT_HISTORY',          Null From dual Union All
          Select 'PERSON',                   'PERSON',                   Null From dual Union All
          Select 'PMPD_PAY_DOC',             'PMPD_PAY_DOC',             1    From dual Union All
          Select 'PMDL_DOC_LIST',            'PMDL_DOC_LIST',            2    From dual Union All
          Select 'PNAP_ACT_PRT',             'PNAP_ACT_PRT_2',           Null From dual Union All
          Select 'PNPD_DOCUMENT',            'PNPD_DOCUMENT',            Null From dual Union All
          Select 'PNPD_PAYMENT_DEPENDANT',   'PNPD_PAYMENT_DEPENDANT',   Null From dual Union All
          Select 'PNPT_PAYMENT',             'PNPT_PAYMENT',             Null From dual Union All
          Select 'SS_DATA',                  'SS_DATA',                  Null From dual Union All
          Select 'SS_M_PAY',                 'SS_M_PAY',                 Null From dual Union All
          Select 'SS_M_SOL',                 'SS_M_SOL',                 Null From dual Union All
          Select 'SS_M_SOL_ST',              'SS_M_SOL_ST',              Null From dual Union All
          Select 'SS_Z_DOC',                 'SS_Z_DOC',                 Null From dual Union All
          Select 'VIRTUAL_DOC_LIST',         'VIRTUAL_DOC_LIST',         Null From dual) n
   Where Not Exists (Select 1
            From s_load_table t
           Where upper(Coalesce(t.dst_name, t.src_name, t.ldr_name)) = n.dst_name);
-- проверить, что вставилось, и только потом: commit;
