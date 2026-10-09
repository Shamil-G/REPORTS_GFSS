-- Группа загрузки для batch_upload_table.Run_Groups: таблицы одной группы грузятся вместе, внутри группы - по id.
-- Выполнить ДО установки новой версии пакета: без колонки пакет не скомпилируется.
alter table sswh.load_tables_status add group_num number(4);
comment on column sswh.load_tables_status.group_num
  is 'batch_upload_table.Run_Groups: номер группы загрузки, внутри группы порядок по id; пусто - таблица не в группе';
