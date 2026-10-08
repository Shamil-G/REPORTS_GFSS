-- Разовая корректировка s_load_table: строки, исключённые в v_load_table списком id,
-- отключаются штатно - period = 'N'. Прежнее значение period пишется в log_load_tables,
-- по нему можно вернуть строку в загрузку.
-- Выполнить ДО установки новой версии batch_upload_table: в пакете списка исключений нет.
Declare
  cObject Constant Varchar2(32) := 'S_LOAD_TABLE';
  p_Cnt   Pls_Integer := 0;
Begin
  For r In (Select t.id, t.period, Coalesce(t.dst_name, t.src_name, t.ldr_name) name
              From s_load_table t
             Where t.id In (2, 19, 18, 71, 74, 78, 117, 121, 122, 123, 124, 135, 136, 137, 138, 132, 133, 134, 150, 151)
               And t.period != 'N'
             Order By t.id)
  Loop
    Update s_load_table t Set t.period = 'N' Where t.id = r.id;
    Insert Into log_load_tables
      (atime, object, action, info)
    Values
      (Current_Timestamp, cObject, 'period -> N', 'id=' || r.id || ', period=' || r.period || ', ' || r.name);
    p_Cnt := p_Cnt + 1;
  End Loop;
  Commit;
  dbms_output.put_line('Отключено строк: ' || p_Cnt);
End;
/
