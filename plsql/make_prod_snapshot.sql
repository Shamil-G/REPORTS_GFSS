create or replace procedure make_prod_snapshot authid current_user is
  -- Слепок кода и метаданных для проверок: таблицы prod_* в схеме того, кто запускает,
  -- из того, что он видит в all_*. Системные схемы Oracle не берутся.
  -- Повторный запуск пересоздаёт таблицы.
  cOwners constant varchar2(200) := 'owner in (select username from all_users where oracle_maintained = ''N'')';

  procedure snap(iTable varchar2, iSelect varchar2) is
  begin
    begin
      execute immediate 'drop table ' || iTable || ' purge';
    exception
      when others then
        if sqlcode != -942 then -- таблицы ещё нет
          raise;
        end if;
    end;
    execute immediate 'create table ' || iTable || ' as ' || iSelect;
  end;
begin
  snap('prod_source',
       'select owner, name, type, line, text from all_source where ' || cOwners);
  snap('prod_objects',
       'select owner, object_name, object_type, status, created, last_ddl_time from all_objects where ' || cOwners);
  snap('prod_dependencies',
       'select owner, name, type, referenced_owner, referenced_name, referenced_type from all_dependencies where ' || cOwners);
  snap('prod_jobs',
       'select owner, job_name, job_action, repeat_interval, enabled from all_scheduler_jobs where ' || cOwners);
end make_prod_snapshot;
/
