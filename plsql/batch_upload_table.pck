CREATE OR REPLACE Package batch_upload_table Is
  -- Загрузка таблиц по настройкам s_load_table. Заменяет move_obj.Mv_Tabs.
  -- iStream   - поток LOADER (loader.load_table.period), например 'STREAM_REF';
  --             грузятся только источники, которые LOADER загрузил успешно (state = 2)
  -- iDst_Name - необязательный фильтр по началу имени приёмника (ручная перезагрузка одной таблицы)
  -- Пакет грузит только приёмники, которым load_tables_status.load_type выставлен вручную в P или M.
  -- Новые приёмники потока Load(iStream) и Register(iStream) заводят в load_tables_status с load_type = 'X' -
  -- такие не грузятся, пока им не выставят P или M. Строки без load_type (их грузит что-то другое)
  -- пакет не трогает. Дальше P/M уточняется сам:
  --   P - очистка (таблицы или партиций) и вставка; больше cMerge_Max строк
  --   M - merge по уникальному ключу и удаление строк, которых нет в источнике;
  --       без уникального ключа - сверка по всем колонкам: лишние строки удаляются, новые добавляются
  -- Run (для джоба) грузит приёмник, если источник загружен в LOADER успешно и позже нашей последней
  -- загрузки, а наша последняя загрузка не упала; после ошибки приёмник ждёт разбора (state != 2).

  -- приёмники к загрузке: то же, что v_load_table, но без списка исключений по id -
  -- отключённые строки s_load_table имеют period = 'N'
  -- iStream = Null - все потоки; iReady = 1 - только готовые к загрузке по правилу Run
  Cursor cDst
  (
    iStream   Varchar2,
    iDst_Name Varchar2,
    iReady    Number := 0
  ) Is
    Select *
      From (Select dt.id,
                   dt.ord,
                   Nvl(dt.src_owner, 'LOADER') src_owner,
                   Nvl(dt.src_name, dt.ldr_name) src_name,
                   Nvl(dt.src_owner, 'LOADER') || '.' || Nvl(dt.src_name, dt.ldr_name) src_full_name,
                   lt.dpart_name_1 src_p1,
                   lt.dpart_name_2 src_p2,
                   Nvl(dt.dst_owner, User) dst_owner,
                   Coalesce(dt.dst_name, dt.src_name, dt.ldr_name) dst_name,
                   Nvl(dt.dst_owner, User) || '.' || Coalesce(dt.dst_name, dt.src_name, dt.ldr_name) dst_full_name,
                   Nvl(st.partitioned, 'NO') partitioned,
                   dt.dst_p1,
                   dt.dst_p2,
                   Nvl(dt.cond, '1 = 1') cond,
                   ls.load_type,
                   ls.state ls_state,
                   ls.end_time ls_end,
                   ls.loaded_rows ls_rows,
                   lt.period stream,
                   lst.state ldr_state,
                   lst.end_time ldr_end,
                   lst.loaded_rows ldr_rows
              From s_load_table dt, loader.load_table lt, dba_tables st, load_tables_status ls,
                   loader.load_tables_status lst
             Where dt.period != 'N'
               And lt.dtable_name = dt.ldr_name
               And lt.is_remote = 'N'
               And substr(lt.period, 1, 7) = 'STREAM_'
               And st.owner(+) = Nvl(dt.dst_owner, User)
               And st.table_name(+) = Coalesce(dt.dst_name, dt.src_name, dt.ldr_name)
               And ls.table_name = upper(Coalesce(dt.dst_name, dt.src_name, dt.ldr_name))
               And ls.load_type In ('P', 'M')
               And lst.table_name(+) = lt.dtable_name) t
     Where (iStream Is Null Or upper(t.stream) = upper(iStream))
       And t.dst_name Like iDst_Name || '%'
       And t.ldr_state = 2
       And (iReady = 0 Or t.ldr_end > Nvl(t.ls_end, date '1900-01-01') And Nvl(t.ls_state, 2) = 2)
     Order By t.src_full_name, t.ord Nulls Last, t.dst_full_name;

  Type TDstList Is Table Of cDst%Rowtype;

  -- ручная загрузка потока: без проверки свежести источника и состояния прошлой загрузки
  Procedure Load
  (
    iStream   Varchar2,
    iDst_Name Varchar2 := Null
  );

  -- для джоба потока (JOB_UPLOAD_REF -> Run('STREAM_REF')): всё, что готово к загрузке;
  -- нечего грузить - выход без записей в протокол. Новые таблицы не регистрирует.
  Procedure Run(iStream Varchar2);

  -- завести в load_tables_status новые приёмники потока с load_type = 'X' (не грузятся до P/M);
  -- вызывается и из Load(iStream). Без имени потока не делает ничего.
  Procedure Register(iStream Varchar2);

  -- Предварительная проверка: приёмники, которые загрузит Load(iStream).
  -- Select * From Table(batch_upload_table.table_list('STREAM_REF'));
  Function table_list(iStream Varchar2) Return TDstList
    Pipelined;

End batch_upload_table; -- load_obj
/
CREATE OR REPLACE Package Body batch_upload_table Is

  Type TNames Is Table Of Varchar2(128);

  cObject    Constant Varchar2(32) := 'BATCH_UPLOAD_TABLE'; -- объект в протоколе для всего запуска
  cMerge_Max Constant Number := 10000000; -- до стольких строк приёмник грузится merge (M), больше - P
  cDel_Max   Constant Number := 500000; -- merge: больше удалять нельзя - сбой источника, откат
  cMin_Share Constant Number := 0.5; -- P: LOADER загрузил меньше этой доли от нашей прошлой загрузки - сбой

  p_Ok   Boolean; -- все операции по текущему источнику прошли без ошибок
  p_Rows Pls_Integer; -- число строк, обработанных последней командой Exec
  p_Err  Varchar2(2000); -- первая ошибка по текущему источнику - для load_tables_status

  ---------------------------------------------------------------- протокол
  -- длины в байтах: object Varchar2(64), info Varchar2(4000), база AL32UTF8
  Procedure Log
  (
    iObject Varchar2,
    iAction Varchar2,
    iMsg    Varchar2 := Null
  ) Is
    Pragma Autonomous_Transaction;
  Begin
    Insert Into log_load_tables
      (atime, object, action, info)
    Values
      (Current_Timestamp, substrb(iObject, 1, 64), iAction, substrb(iMsg, 1, 4000));
    Commit;
  End;

  -- Ошибка по текущему источнику: в протокол, сбросить p_Ok, первую запомнить в p_Err
  Procedure Fail
  (
    iObject Varchar2,
    iErr    Varchar2,
    iSql    Varchar2 := Null
  ) Is
  Begin
    p_Ok := False;
    If p_Err Is Null Then
      p_Err := substrb(iObject || ': ' || iErr, 1, 2000);
    End If;
    Log(iObject, 'Ошибка !', iErr || Case When iSql Is Not Null Then ' | ' || iSql End);
  End;

  -- Выполнить команду. В протокол пишется только ошибка - вместе с текстом команды;
  -- загрузка при этом не прерывается, сбрасывается p_Ok.
  Procedure Exec
  (
    iObject Varchar2,
    iSql    Varchar2
  ) Is
  Begin
    Execute Immediate iSql;
    p_Rows := Sql%Rowcount;
  Exception
    When Others Then
      Fail(iObject, Sqlerrm, iSql);
  End;

  ---------------------------------------------------------------- партиции
  -- переключаемые партиции приёмника (без повторов); имя партиции = 'P' || PART_ID
  Function Parts(d cDst%Rowtype) Return TNames Is
  Begin
    Return TNames(d.src_p1, d.src_p2) Multiset Union Distinct TNames(d.dst_p1, d.dst_p2);
  End;

  -- список значений PART_ID для условия In (...)
  Function Keys(iParts TNames) Return Varchar2 Is
    p_List Varchar2(4000);
  Begin
    For i In 1 .. iParts.Count Loop
      p_List := p_List || ', ''' || substr(iParts(i), 2) || '''';
    End Loop;
    Return substr(p_List, 3);
  End;

  -- уникальный индекс приёмника для merge: PK, если есть, иначе первый по имени; Null - ключа нет
  Function Key_Index(d cDst%Rowtype) Return Varchar2 Is
    p_Name all_indexes.index_name%Type;
  Begin
    Select Max(i.index_name) Keep(Dense_Rank First Order By Nvl2(c.constraint_name, 0, 1), i.index_name)
      Into p_Name
      From all_indexes i, all_constraints c
     Where i.table_owner = upper(d.dst_owner)
       And i.table_name = upper(d.dst_name)
       And i.uniqueness = 'UNIQUE'
       And i.index_type Not Like 'FUNCTION-BASED%'
       And c.owner(+) = i.table_owner
       And c.index_name(+) = i.index_name
       And c.constraint_type(+) = 'P';
    Return p_Name;
  End;

  ---------------------------------------------------------------- load_tables_status
  Procedure Register(iStream Varchar2) Is
    p_Id    load_tables_status.id%Type;
    p_Names Varchar2(4000);
  Begin
    For r In (Select Distinct upper(Coalesce(dt.dst_name, dt.src_name, dt.ldr_name)) table_name
                From s_load_table dt, loader.load_table lt
               Where dt.period != 'N'
                 And lt.dtable_name = dt.ldr_name
                 And lt.is_remote = 'N'
                 And substr(lt.period, 1, 7) = 'STREAM_'
                 And upper(lt.period) = upper(iStream)
                 And Not Exists (Select 1
                        From load_tables_status ls
                       Where ls.table_name = upper(Coalesce(dt.dst_name, dt.src_name, dt.ldr_name))))
    Loop
      Select Nvl(Max(s.id), 0) + 1 Into p_Id From load_tables_status s;
      Insert Into load_tables_status
        (id, table_name, load_type, info)
      Values
        (p_Id, r.table_name, 'X', 'Новая, заведена batch_upload_table');
      p_Names := substrb(p_Names || ', ' || r.table_name, 1, 4000);
    End Loop;
    If p_Names Is Not Null Then
      Commit;
      Log(cObject, 'Новые таблицы (X)', iStream || ': ' || substr(p_Names, 3));
    End If;
  End;

  -- table_name = имя приёмника без владельца; строка с load_type заведена вручную
  Procedure Status_Beg(d cDst%Rowtype) Is
    Pragma Autonomous_Transaction;
  Begin
    Update load_tables_status s
       Set s.state = 1, s.beg_time = Sysdate, s.end_time = Null, s.info = 'Начата обработка'
     Where s.table_name = upper(d.dst_name);
    Commit;
  End;

  -- число строк в приёмнике после загрузки: в партиционированном - только в переключаемых партициях
  Function Dst_Rows(d cDst%Rowtype) Return Number Is
    p_Sql Varchar2(4000) := 'Select Count(*) From ' || d.dst_full_name;
    p_Cnt Number;
  Begin
    If d.partitioned = 'YES' Then
      p_Sql := p_Sql || ' Where PART_ID In (' || Keys(Parts(d)) || ')';
    End If;
    Execute Immediate p_Sql
      Into p_Cnt;
    Return p_Cnt;
  End;

  -- итог по всем приёмникам источника: p_Ok - успех, число строк и тип следующей загрузки,
  -- иначе ошибка p_Err. iRows - сколько вставил Insert All: одно число на все приёмники P,
  -- поэтому при нескольких таких приёмниках и для приёмников M строки считаются.
  Procedure Status_End
  (
    iDst  TDstList,
    iRows Number
  ) Is
    Pragma Autonomous_Transaction;
    p_NP   Pls_Integer := 0; -- приёмников P
    p_Cnt  Number;
    p_Type Varchar2(1);
  Begin
    For i In 1 .. iDst.Count Loop
      If iDst(i).load_type = 'P' Then
        p_NP := p_NP + 1;
      End If;
    End Loop;
    For i In 1 .. iDst.Count Loop
      If p_Ok Then
        If iDst(i).load_type = 'P' And p_NP = 1 Then
          p_Cnt := iRows;
        Else
          p_Cnt := Dst_Rows(iDst(i));
        End If;
        If p_Cnt > cMerge_Max Then
          p_Type := 'P';
        Else
          p_Type := 'M';
        End If;
        If p_Type != iDst(i).load_type Then
          Log(iDst(i).dst_full_name, 'Тип загрузки', iDst(i).load_type || ' -> ' || p_Type || ', строк ' || p_Cnt);
        End If;
        Update load_tables_status s
           Set s.state = 2, s.end_time = Sysdate, s.last_success_date = Sysdate, s.loaded_rows = p_Cnt,
               s.info = Null, s.load_type = p_Type
         Where s.table_name = upper(iDst(i).dst_name);
      Else
        Update load_tables_status s
           Set s.state = 8, s.end_time = Sysdate, s.info = p_Err
         Where s.table_name = upper(iDst(i).dst_name);
      End If;
    End Loop;
    Commit;
  End;

  ---------------------------------------------------------------- приёмник
  -- добавить недостающие переключаемые партиции
  Procedure Add_Parts(d cDst%Rowtype) Is
    p_Parts TNames := Parts(d);
    p_Cnt   Pls_Integer;
  Begin
    For i In 1 .. p_Parts.Count Loop
      Select Count(*)
        Into p_Cnt
        From all_tab_partitions tp
       Where tp.table_owner = upper(d.dst_owner)
         And tp.table_name = upper(d.dst_name)
         And tp.partition_name = upper(p_Parts(i));
      If p_Cnt = 0 Then
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Add Partition ' || p_Parts(i) ||
             ' Values (''' || substr(p_Parts(i), 2) || ''')');
      End If;
    End Loop;
  End;

  -- P, до вставки: очистить приёмник, отключить индексы и констрейнты
  Procedure Prepare_Dst(d cDst%Rowtype) Is
    p_Parts TNames;
  Begin
    If d.partitioned = 'YES' Then
      Add_Parts(d);
      p_Parts := Parts(d);
      For i In 1 .. p_Parts.Count Loop
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Modify Partition ' || p_Parts(i) ||
             ' Unusable Local Indexes');
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Truncate Partition ' || p_Parts(i));
      End Loop;
    Else
      -- сначала констрейнты: при отключении PK его индекс удаляется
      For c In (Select a.constraint_name
                  From all_constraints a
                 Where a.owner = upper(d.dst_owner)
                   And a.table_name = upper(d.dst_name))
      Loop
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Disable Constraint ' || c.constraint_name);
      End Loop;
      For x In (Select a.owner, a.index_name
                  From all_indexes a
                 Where a.table_owner = upper(d.dst_owner)
                   And a.table_name = upper(d.dst_name))
      Loop
        Exec(d.dst_full_name,
             'Alter Index ' || x.owner || '.' || x.index_name || ' Unusable');
      End Loop;
      Exec(d.dst_full_name, 'Truncate Table ' || d.dst_full_name || ' Drop Storage');
    End If;
  End;

  -- P, после вставки: перестроить индексы, включить констрейнты
  Procedure Finish_Dst(d cDst%Rowtype) Is
    p_Parts TNames;
  Begin
    If d.partitioned = 'YES' Then
      p_Parts := Parts(d);
      For i In 1 .. p_Parts.Count Loop
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Modify Partition ' || p_Parts(i) ||
             ' Rebuild Unusable Local Indexes');
      End Loop;
    Else
      For x In (Select a.owner, a.index_name
                  From all_indexes a
                 Where a.table_owner = upper(d.dst_owner)
                   And a.table_name = upper(d.dst_name)
                   And a.status = 'UNUSABLE')
      Loop
        Exec(d.dst_full_name,
             'Alter Index ' || x.owner || '.' || x.index_name || ' Rebuild');
      End Loop;
      For c In (Select a.constraint_name
                  From all_constraints a
                 Where a.owner = upper(d.dst_owner)
                   And a.table_name = upper(d.dst_name)
                   And a.status = 'DISABLED')
      Loop
        Exec(d.dst_full_name,
             'Alter Table ' || d.dst_full_name || ' Enable Constraint ' || c.constraint_name);
      End Loop;
    End If;
  End;

  -- M: удаление строк, которых нет в источнике, и merge по уникальному ключу - одной транзакцией.
  -- Обновляются только строки, в которых изменилась хотя бы одна колонка (Null = Null).
  -- Без уникального ключа строка определяется всеми колонками: удаляются строки, которых нет
  -- в источнике, и добавляются строки источника, которых нет в приёмнике.
  -- PART_ID - номер партиции LOADER, меняется при каждой его загрузке: в ключе и сравнении
  -- не участвует и не обновляется, только записывается в новые строки.
  -- В партиционированном приёмнике - только в переключаемых партициях.
  -- Удалено больше cDel_Max или больше, чем пришло из источника, - сбой источника: откат и ошибка.
  Procedure Merge_Dst
  (
    iSrc Varchar2,
    d    cDst%Rowtype
  ) Is
    p_Index all_indexes.index_name%Type := Key_Index(d);
    p_Need  Pls_Integer; -- колонок в ключе
    p_Keys  Pls_Integer := 0; -- из них нашлось в источнике
    p_Cols  Varchar2(32767);
    p_Vals  Varchar2(32767);
    p_Set   Varchar2(32767);
    p_Diff  Varchar2(32767); -- условие "строка изменилась"
    p_On    Varchar2(32767);
    p_Src   Varchar2(32767);
    p_In    Number; -- пришло строк из источника
    p_Mrg   Number; -- изменено и добавлено строк (без ключа - добавлено)
    p_Del   Number; -- удалено строк
  Begin
    For c In (Select s.column_name,
                     dc.nullable,
                     dc.data_type,
                     (Select Count(*)
                        From all_ind_columns ic
                       Where ic.table_owner = dc.owner
                         And ic.table_name = dc.table_name
                         And ic.index_name = p_Index
                         And ic.column_name = s.column_name) is_key
                From all_tab_columns s, all_tab_columns dc
               Where s.owner = upper(d.src_owner)
                 And s.table_name = upper(d.src_name)
                 And dc.owner = upper(d.dst_owner)
                 And dc.table_name = upper(d.dst_name)
                 And dc.column_name = s.column_name
               Order By s.column_id)
    Loop
      p_Cols := p_Cols || ', ' || c.column_name;
      p_Vals := p_Vals || ', s.' || c.column_name;
      If c.column_name = 'PART_ID' Then
        p_Keys := p_Keys + Sign(c.is_key);
      Elsif c.is_key > 0 Then
        p_Keys := p_Keys + 1;
        If c.nullable = 'Y' Then
          p_On := p_On || ' And (t.' || c.column_name || ' = s.' || c.column_name ||
                  ' Or t.' || c.column_name || ' Is Null And s.' || c.column_name || ' Is Null)';
        Else
          p_On := p_On || ' And t.' || c.column_name || ' = s.' || c.column_name;
        End If;
      Else
        p_Set := p_Set || ', t.' || c.column_name || ' = s.' || c.column_name;
        If c.data_type In ('CLOB', 'NCLOB', 'BLOB') Then
          -- Decode с LOB не работает
          p_Diff := p_Diff || ' Or Nvl(dbms_lob.compare(t.' || c.column_name || ', s.' || c.column_name ||
                    '), 1) != 0 And (t.' || c.column_name || ' Is Not Null Or s.' || c.column_name || ' Is Not Null)';
        Else
          p_Diff := p_Diff || ' Or Decode(t.' || c.column_name || ', s.' || c.column_name || ', 0, 1) = 1';
        End If;
      End If;
    End Loop;
    Select Count(*)
      Into p_Need
      From all_ind_columns ic
     Where ic.table_owner = upper(d.dst_owner)
       And ic.table_name = upper(d.dst_name)
       And ic.index_name = p_Index;
    If p_Keys < p_Need Then
      Fail(d.dst_full_name, 'Merge невозможен: не все колонки ключа ' || p_Index || ' есть в источнике ' || iSrc);
      Return;
    End If;
    p_On := substr(p_On, 6);
    If p_On Is Null Then
      p_Index := Null; -- ключ из одного PART_ID - сверка по всем колонкам
    End If;
    p_Src := '(Select ' || substr(p_Cols, 3) || ' From ' || iSrc || ' Where (' || d.cond || ')';
    If d.partitioned = 'YES' Then
      p_Src := p_Src || ' And PART_ID In (' || Keys(Parts(d)) || ')';
    End If;
    p_Src := p_Src || ')';
    Execute Immediate 'Select Count(*) From ' || p_Src
      Into p_In;
    If p_Index Is Null Then
      p_On := 'Not (' || substr(p_Diff, 5) || ')'; -- строки совпадают по всем колонкам
    End If;
    -- 1. удалить строки, которых нет в источнике
    p_Rows := Null;
    Exec(d.dst_full_name,
         'Delete From ' || d.dst_full_name || ' t' || chr(10) ||
         'Where Not Exists (Select 1 From ' || p_Src || ' s Where ' || p_On || ')' ||
         Case When d.partitioned = 'YES' Then chr(10) || 'And t.PART_ID In (' || Keys(Parts(d)) || ')' End);
    If p_Rows Is Null Then
      Rollback;
      Return;
    End If;
    p_Del := p_Rows;
    -- 2. с ключом - merge, без ключа - добавить строки источника, которых нет в приёмнике
    p_Rows := Null;
    If p_Index Is Not Null Then
      Exec(d.dst_full_name,
           'Merge Into ' || d.dst_full_name || ' t' || chr(10) || 'Using ' || p_Src || ' s' || chr(10) ||
           'On (' || p_On || ')' || chr(10) ||
           Case When p_Set Is Not Null Then
             'When Matched Then Update Set ' || substr(p_Set, 3) || chr(10) || ' Where ' || substr(p_Diff, 5) || chr(10)
           End ||
           'When Not Matched Then Insert (' || substr(p_Cols, 3) || ') Values (' || substr(p_Vals, 3) || ')');
    Else
      Exec(d.dst_full_name,
           'Insert Into ' || d.dst_full_name || ' (' || substr(p_Cols, 3) || ')' || chr(10) ||
           'Select ' || substr(p_Vals, 3) || ' From ' || p_Src || ' s' || chr(10) ||
           'Where Not Exists (Select 1 From ' || d.dst_full_name || ' t Where ' || p_On || ')');
    End If;
    If p_Rows Is Null Then
      Rollback;
      Return;
    End If;
    p_Mrg := p_Rows;
    If p_Del > cDel_Max Or p_Del > p_In Then
      Rollback;
      Fail(d.dst_full_name, 'Удаляется ' || p_Del || ' строк при ' || p_In || ' пришедших (предел ' || cDel_Max ||
           '): похоже на сбой источника ' || iSrc || ', merge отменён');
      Return;
    End If;
    Commit;
    Log(d.dst_full_name, 'Merge завершён',
        'Пришло ' || p_In || Case When p_Index Is Null Then ', сверка по всем колонкам: добавлено '
                                  Else ', по ключу ' || p_Index || ': изменено и добавлено ' End ||
        p_Mrg || ', удалено ' || p_Del);
  Exception
    When Others Then
      Rollback;
      Fail(d.dst_full_name, Sqlerrm);
  End;

  ---------------------------------------------------------------- источник
  -- Insert All: по ветке When на каждый приёмник, вставляются общие колонки
  Function Insert_Sql
  (
    iSrc Varchar2,
    iDst TDstList
  ) Return Varchar2 Is
    p_Sql      Varchar2(32767);
    p_Cols     Varchar2(32767);
    p_Parts    TNames;
    p_AllParts TNames := TNames();
    p_AllPart  Boolean := True; -- все приёмники партиционированы
  Begin
    For i In 1 .. iDst.Count Loop
      Select listagg(s.column_name, ', ') within Group(Order By s.column_id)
        Into p_Cols
        From all_tab_columns s, all_tab_columns d
       Where s.owner = upper(iDst(i).src_owner)
         And s.table_name = upper(iDst(i).src_name)
         And d.owner = upper(iDst(i).dst_owner)
         And d.table_name = upper(iDst(i).dst_name)
         And d.column_name = s.column_name;
      p_Sql := p_Sql || chr(10) || 'When (' || iDst(i).cond || ')';
      If iDst(i).partitioned = 'YES' Then
        -- в партиционированный приёмник - только строки его партиций
        p_Parts    := Parts(iDst(i));
        p_Sql      := p_Sql || ' And PART_ID In (' || Keys(p_Parts) || ')';
        p_AllParts := p_AllParts Multiset Union Distinct p_Parts;
      Else
        p_AllPart := False;
      End If;
      p_Sql := p_Sql || ' Then Into ' || iDst(i).dst_full_name || chr(10) || ' (' || p_Cols || ')' ||
               chr(10) || ' Values' || chr(10) || ' (' || p_Cols || ')';
    End Loop;
    p_Sql := 'Insert /*+APPEND*/ All' || p_Sql || chr(10) || 'Select * From ' || iSrc;
    If p_AllPart Then
      -- все приёмники партиционированы - читаем из источника только нужные партиции
      p_Sql := p_Sql || chr(10) || 'Where PART_ID In (' || Keys(p_AllParts) || ')';
    End If;
    Return p_Sql;
  End;

  Procedure Load_Source
  (
    iSrc Varchar2,
    iDst TDstList
  ) Is
    p_Dst   TDstList := iDst;
    p_PDst  TDstList := TDstList(); -- приёмники P - для Insert All
    p_Names Varchar2(4000);
    p_Ins   Number; -- вставлено строк во все приёмники P
    -- объект в протоколе: приёмник, а если их у источника несколько - источник
    p_Obj Varchar2(261) := Case When iDst.Count = 1 Then iDst(1).dst_full_name Else iSrc End;
  Begin
    p_Ok  := True;
    p_Err := Null;
    Log(p_Obj, 'Начало загрузки', 'Из ' || iSrc);
    -- 0. P: источник подозрительно мал по сравнению с прошлой загрузкой - приёмники не трогаем
    For i In 1 .. p_Dst.Count Loop
      If p_Dst(i).load_type = 'P' And p_Dst(i).ls_rows > 0 And
         Nvl(p_Dst(i).ldr_rows, 0) < p_Dst(i).ls_rows * cMin_Share Then
        Fail(p_Obj, 'Источник подозрительно мал: LOADER загрузил ' || Nvl(p_Dst(i).ldr_rows, 0) || ', в ' ||
             p_Dst(i).dst_full_name || ' было ' || p_Dst(i).ls_rows || ' (порог ' || cMin_Share * 100 || '%)');
      End If;
    End Loop;
    If Not p_Ok Then
      Log(p_Obj, 'Загрузка отменена');
      Status_End(p_Dst, Null);
      Return;
    End If;
    -- 1. подготовить приёмники: P - очистить, M - только добавить партиции
    For i In 1 .. p_Dst.Count Loop
      Status_Beg(p_Dst(i));
      If p_Dst(i).load_type = 'P' Then
        Prepare_Dst(p_Dst(i));
        p_PDst.Extend;
        p_PDst(p_PDst.Count) := p_Dst(i);
      Elsif p_Dst(i).partitioned = 'YES' Then
        Add_Parts(p_Dst(i));
      End If;
      p_Names := p_Names || ', ' || Case When p_Dst.Count > 1 Then p_Dst(i).dst_full_name || ' ' End ||
                 '(' || p_Dst(i).load_type || ')';
    End Loop;
    Log(p_Obj, 'Приёмники подготовлены', substr(p_Names, 3));
    If p_PDst.Count > 0 Then
      -- 2. P: одна вставка во все такие приёмники
      Begin
        p_Rows := Null;
        Exec(p_Obj, Insert_Sql(iSrc, p_PDst));
        Commit;
        p_Ins := p_Rows;
        If p_Ins Is Not Null Then
          Log(p_Obj, 'Вставка завершена', 'Загружено ' || p_Ins || ' записей');
        End If;
      Exception
        When Others Then
          -- ошибка при сборке команды (выполнение ловит Exec)
          Fail(p_Obj, Sqlerrm);
      End;
      -- 3. P: вернуть индексы и констрейнты
      For i In 1 .. p_PDst.Count Loop
        Finish_Dst(p_PDst(i));
      End Loop;
    End If;
    -- 4. M: merge в каждый такой приёмник
    For i In 1 .. p_Dst.Count Loop
      If p_Dst(i).load_type = 'M' Then
        Merge_Dst(iSrc, p_Dst(i));
      End If;
    End Loop;
    -- 5. всё успешно - переключаем имена партиций
    If p_Ok Then
      For i In 1 .. p_Dst.Count Loop
        If p_Dst(i).partitioned = 'YES' Then
          Update s_load_table t
             Set t.dst_p1 = p_Dst(i).src_p1, t.dst_p2 = p_Dst(i).src_p2
           Where t.id = p_Dst(i).id;
        End If;
      End Loop;
      Commit;
      Log(p_Obj, 'Загрузка завершена');
    Else
      Log(p_Obj, 'Загрузка завершена с ошибками');
    End If;
    Status_End(p_Dst, p_Ins);
  Exception
    When Others Then
      Fail(p_Obj, Sqlerrm);
      Status_End(p_Dst, p_Ins);
  End;

  ---------------------------------------------------------------- точка входа
  Procedure Do_Load
  (
    iStream   Varchar2,
    iDst_Name Varchar2,
    iReady    Number
  ) Is
    p_All TDstList; -- все приёмники, упорядочены по источнику
    p_Dst TDstList := TDstList(); -- приёмники текущего источника
    p_Cnt Pls_Integer := 0; -- обработано источников
    p_Bad Pls_Integer := 0; -- из них с ошибками
  Begin
    If iReady = 0 Then
      Register(iStream);
    End If;
    Open cDst(iStream, iDst_Name, iReady);
    Fetch cDst Bulk Collect
      Into p_All;
    Close cDst;
    If iReady = 1 And p_All.Count = 0 Then
      Return; -- джобу нечего грузить
    End If;
    Log(cObject, 'Начало загрузки',
        Case When iReady = 1 Then 'Run ' End || 'Stream=' || iStream ||
        Case When iDst_Name Is Not Null Then ', Dst=' || iDst_Name End);
    For i In 1 .. p_All.Count Loop
      p_Dst.Extend;
      p_Dst(p_Dst.Count) := p_All(i);
      -- последний приёмник источника - загружаем источник
      If i = p_All.Count Or p_All(i + 1).src_full_name != p_All(i).src_full_name Then
        dbms_application_info.set_client_info('Loading ' || p_All(i).src_full_name);
        Load_Source(p_All(i).src_full_name, p_Dst);
        p_Dst := TDstList();
        p_Cnt := p_Cnt + 1;
        If Not p_Ok Then
          p_Bad := p_Bad + 1;
        End If;
      End If;
    End Loop;
    Log(cObject, 'Загрузка завершена', 'Источников: ' || p_Cnt || ', с ошибками: ' || p_Bad);
  Exception
    When Others Then
      -- курсор уровня пакета остаётся открытым до конца сессии
      If cDst%Isopen Then
        Close cDst;
      End If;
      Log(cObject, 'Ошибка !', Sqlerrm);
      Raise;
  End;

  Procedure Load
  (
    iStream   Varchar2,
    iDst_Name Varchar2 := Null
  ) Is
  Begin
    Do_Load(iStream, iDst_Name, 0);
  End;

  Procedure Run(iStream Varchar2) Is
  Begin
    Do_Load(iStream, Null, 1);
  End;

  Function table_list(iStream Varchar2) Return TDstList
    Pipelined Is
  Begin
    For r In cDst(iStream, Null) Loop
      Pipe Row(r);
    End Loop;
    Return;
  End;

End batch_upload_table;
/
