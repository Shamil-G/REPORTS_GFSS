-- Джоб загрузки групп SSWH из LOADER: batch_upload_table.Make обходит группы load_tables_status.group_num,
-- внутри группы - таблицы по id. Группа грузится, если её первую таблицу LOADER обновил успешно
-- позже нашей последней загрузки и у таблиц группы нет неразобранных ошибок.
-- Время (repeat_interval, start_date) выставить своё - после вечерних потоков LOADER,
-- чтобы не работать одновременно с ними.
-- Создаётся выключенным: включить после проверки.
begin
  sys.dbms_scheduler.create_job(job_name        => 'SSWH.JOB_UPLOAD_GROUPS',
                                job_type        => 'PLSQL_BLOCK',
                                job_action      => 'begin batch_upload_table.Make; end;',
                                start_date      => to_date('10-10-2026 03:00:00', 'dd-mm-yyyy hh24:mi:ss'),
                                repeat_interval => 'Freq=Daily;ByHour=03;ByMinute=00',
                                end_date        => to_date(null),
                                job_class       => 'DEFAULT_JOB_CLASS',
                                enabled         => false,
                                auto_drop       => false,
                                comments        => 'Загрузка групп таблиц из LOADER (batch_upload_table.Make)');
end;
/
-- включить:
-- begin sys.dbms_scheduler.enable('SSWH.JOB_UPLOAD_GROUPS'); end;
-- запустить разово сейчас, в своей сессии:
-- begin sys.dbms_scheduler.run_job('SSWH.JOB_UPLOAD_GROUPS', use_current_session => true); end;
