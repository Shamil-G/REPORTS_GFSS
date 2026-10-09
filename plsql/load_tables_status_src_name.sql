-- Настройка загрузки batch_upload_table переезжает из s_load_table в load_tables_status.
-- Выполнить ДО установки новой версии пакета: без колонок пакет не скомпилируется.
alter table sswh.load_tables_status add src_name varchar2(30);
comment on column sswh.load_tables_status.src_name
  is 'batch_upload_table: таблица-источник в LOADER; пусто - одноимённая таблица';

-- 1. из s_load_table: таблица LOADER, только если её имя отличается от приёмника
Update load_tables_status ls
   Set src_name =
       (Select Nullif(upper(Max(dt.ldr_name)), ls.table_name)
          From s_load_table dt
         Where upper(Coalesce(dt.dst_name, dt.src_name, dt.ldr_name)) = ls.table_name)
 Where Exists (Select 1
          From s_load_table dt
         Where upper(Coalesce(dt.dst_name, dt.src_name, dt.ldr_name)) = ls.table_name);

-- 2. PNAP_ACT_PRT_2: строки в s_load_table нет, пакет LOAD_PNAP_ACT_PRT_2 грузит из loader.pnap_act_prt
Update load_tables_status Set src_name = 'PNAP_ACT_PRT' Where table_name = 'PNAP_ACT_PRT_2';

-- проверить и только потом commit:
-- select table_name, load_type, group_num, src_name from load_tables_status
--  where load_type in ('P', 'M', 'X') or src_name is not null order by table_name;
-- src_name должен быть заполнен только там, где таблица LOADER называется иначе (около 5 строк).
