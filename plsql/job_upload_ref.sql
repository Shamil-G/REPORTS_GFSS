-- Джоб загрузки справочников SSWH из LOADER, пара к LOADER.JOB_LOAD_REF:
-- batch_upload_table.Run('STREAM_REF') грузит таблицы P/M потока, которые LOADER
-- обновил успешно позже нашей последней загрузки.
-- Время - после всех вечерних потоков LOADER, чтобы не работать одновременно с ними.
-- Создаётся выключенным: включить после проверки.
begin
  sys.dbms_scheduler.create_job(job_name        => 'SSWH.JOB_UPLOAD_REF',
                                job_type        => 'PLSQL_BLOCK',
                                job_action      => 'begin batch_upload_table.Run(''STREAM_REF''); end;',
                                start_date      => to_date('09-10-2026 03:00:00', 'dd-mm-yyyy hh24:mi:ss'),
                                repeat_interval => 'Freq=Daily;ByHour=03;ByMinute=00',
                                end_date        => to_date(null),
                                job_class       => 'DEFAULT_JOB_CLASS',
                                enabled         => false,
                                auto_drop       => false,
                                comments        => 'Загрузка справочников из LOADER (STREAM_REF), пара к LOADER.JOB_LOAD_REF');
end;
/
-- включить:
-- begin sys.dbms_scheduler.enable('SSWH.JOB_UPLOAD_REF'); end;
-- запустить разово сейчас, в своей сессии:
-- begin sys.dbms_scheduler.run_job('SSWH.JOB_UPLOAD_REF', use_current_session => true); end;
