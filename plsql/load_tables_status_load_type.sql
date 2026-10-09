-- Способ загрузки приёмника для batch_upload_table. Выполнить ДО установки новой версии пакета:
-- без колонки пакет не скомпилируется.
alter table sswh.load_tables_status add load_type varchar2(1);
comment on column sswh.load_tables_status.load_type
  is 'batch_upload_table: M - merge, P - очистка и вставка; пусто - P. Выставляется пакетом после загрузки';
