CREATE OR REPLACE Package batch_upload_table Is
  --
  -- Цель: Загружать таблицы потоками, как это сейчас делает LOADER
  -- Потоки - это строковые константы, записанные для каждой загружаемой таблицы в колонку таблицы LOADER.LAOAD_TABLE.PERIOD
  --
  -- Первая таблица в группе определяется по наименньшему order_num

  -- Загрузка таблиц SSWH из LOADER по настройкам load_tables_status. Заменяет move_obj.Mv_Tabs
  -- (s_load_table пакет не читает). Источник приёмника - LOADER.<src_name>, пусто - одноимённая таблица.
  -- Нет такой таблицы в потоках LOADER - таблица строится из таблиц SSWH (своя LOAD_<таблица>.MAKE, в группах).
  -- iStream   - поток LOADER (loader.load_table.period), например 'STREAM_REF';
  --             грузятся только источники, которые LOADER загрузил успешно (state = 2)
  -- iDst_Name - необязательный фильтр по началу имени приёмника (ручная перезагрузка одной таблицы)
  -- Способ загрузки - load_tables_status.load_type:
  --   P, M - грузит сам пакет (выставляются вручную, дальше P/M уточняется сам, см. ниже);
  --   пусто - своя процедура LOAD_<table_name>.MAKE, если такая есть (в протоколе и table_list - L);
  --           статус по таким таблицам ведёт она сама (load_procedurs), пакет его не пишет;
  --   X - новая таблица, не грузится, пока ей не выставят P, M или не очистят load_type.
  -- Новые таблицы потока LOADER Load(iStream) и Register(iStream) заводят в load_tables_status с load_type = 'X'.
  --   P - очистка (таблицы или партиций) и вставка; больше cMerge_Max_Rows строк
  --   M - merge по уникальному ключу и удаление строк, которых нет в источнике;
  --       без уникального ключа - сверка по всем колонкам: лишние строки удаляются, новые добавляются
  -- Run (для джоба) грузит приёмник, если источник загружен в LOADER успешно и позже нашей последней
  -- загрузки, а наша последняя загрузка не упала; после ошибки приёмник ждёт разбора (state != 2).
  -- Перед загрузкой каждого источника состояние приёмников перечитывается: пока шли предыдущие
  -- источники, приёмник мог взять в работу или уже загрузить джоб LOAD_<таблица> (см. Skip_Reason).
  -- Группы: load_tables_status.group_name (имя группы) объединяет таблицы, которые грузятся вместе, внутри группы -
  -- по order_num. Их грузит Make (Run по потоку их пропускает), см. описание Make.

  -- приёмники к загрузке: строки load_tables_status, источник которых - локальная таблица потока LOADER
  -- iStream = Null - все потоки; iOnly_Ready = 1 - только готовые к загрузке по правилу Run;
  -- iDst_Exact - один приёмник по точному имени (для Make)
  Cursor cur_load_queue
  (
    iStream     Varchar2,
    iDst_Prefix Varchar2,
    iOnly_Ready Number := 0,
    iDst_Exact  Varchar2 := Null
  ) Is
    Select *
      From (Select ls.order_num,
                   'LOADER' src_owner,
                   lt.dtable_name src_name,
                   'LOADER.' || lt.dtable_name src_full_name,
                   lt.dpart_name_1 src_part_1,
                   lt.dpart_name_2 src_part_2,
                   User dst_owner,
                   ls.table_name dst_name,
                   User || '.' || ls.table_name dst_full_name,
                   Nvl(st.partitioned, 'NO') partitioned,
                   Nvl(ls.load_type, 'L') load_type,
                   Case When ls.load_type Is Null Then User || '.LOAD_' || ls.table_name || '.MAKE' End load_proc,
                   ls.state dst_state,
                   ls.end_time dst_end_time,
                   ls.loaded_rows dst_rows,
                   ls.group_name,
                   lt.period stream,
                   lst.state loader_state,
                   lst.end_time loader_end_time,
                   lst.loaded_rows loader_rows
              From load_tables_status ls, loader.load_table lt, dba_tables st, loader.load_tables_status lst
             Where upper(lt.dtable_name) = Nvl(upper(ls.src_name), ls.table_name)
               And lt.is_remote = 'N'
               And substr(lt.period, 1, 7) = 'STREAM_'
               And st.owner(+) = User
               And st.table_name(+) = ls.table_name
               And (ls.load_type In ('P', 'M') Or
                   ls.load_type Is Null And
                   Exists (Select 1
                             From all_procedures pr
                            Where pr.owner = User
                              And pr.object_name = 'LOAD_' || ls.table_name
                              And pr.procedure_name = 'MAKE'))
               And lst.table_name(+) = lt.dtable_name) t
     Where (iStream Is Null Or upper(t.stream) = upper(iStream))
       And t.dst_name Like iDst_Prefix || '%'
       And t.loader_state = 2
       And (iOnly_Ready = 0 Or t.loader_end_time > Nvl(t.dst_end_time, date '1900-01-01') And Nvl(t.dst_state, 2) = 2)
       And (iDst_Exact Is Null Or upper(t.dst_name) = upper(iDst_Exact))
       And (iDst_Exact Is Not Null Or iOnly_Ready = 0 Or t.group_name Is Null) -- таблицы групп Run пропускает
     -- источники - по наименьшему order_num их приёмников, строки одного источника идут подряд
     Order By Min(t.order_num) Over(Partition By t.src_full_name), t.src_full_name, t.order_num;

  Type TLoadQueue Is Table Of cur_load_queue%Rowtype;

  ------------------------------------------------------------------------------------------------------------------
  -- Для загрузки таблиц у которых нет собственных JOB или которые не имеют собственных LOAD_XXX процедур загрузки
  -- Загрузка таблицы идет либо через 'P'-artition либо через 'M'-erge ветку 
  -- Тип загрузки задан значением в колонке LOADER.LOAD_TABLE.LOAD_TYPE
  
  -- Пакет берет список загружаемых таблиц по имени потока
  -- и если эти таблицы могут быть загружены - они загружаются
  
  -- Поток справочников идентифицируется именем 'STREAM_REF', значит его вызов произойдет через
  -- вызов следующего джоба с именем потока: JOB_UPLOAD_REF -> Run('STREAM_REF');

  -- нечего грузить - выход без записей в протокол. Новые таблицы не регистрирует.
  -- Имя поотока берется из таблицы LOADER.LAOAD_TABLE.PERIOD
  Procedure Run(iStream Varchar2);

  -- ручная загрузка потока: без проверки свежести источника и состояния прошлой загрузки
  Procedure Load
  (
    iStream   Varchar2,
    iDst_Name Varchar2 := Null
  );

  ---------------------------------------------------------------------------------------
  
  ---------------------------------------------------------------------------------------
  --
  -- Для загрузки таблиц, имеющих собственную процедуру загрузки LOAD_XXX
  --
  
  -- Для этого таблицы объединяются в группу, по аналогии с потоками
  -- Группы записаны в колонку SSWH.LOAD_TABLES_STATUS.GROUP_NUM
  
  -- для джоба групп (точка входа, как MAKE у LOAD_*): группы по порядку group_num, внутри группы таблицы по id.
  -- Группа пропускается, если её первая таблица не готова к загрузке по правилу Run или у какой-либо
  -- таблицы группы прошлая загрузка не завершилась успешно (state не 2 и не пусто). На первой ошибке
  -- группа останавливается. Таблица группы без источника в LOADER (строится из таблиц SSWH)
  -- грузится своей LOAD_<таблица>.MAKE; у первой таблицы группы источник в LOADER должен быть.
  -- Таблица группы, которую перед стартом пропустил Skip_Reason (её грузит другой процесс, или P/M
  -- уже загружена после LOADER): первая - пропускается вся группа, остальные - группа идёт дальше.
  -- Нечего грузить - выход без записей в протокол.
  Procedure Make;
  
  ---------------------------------------------------------------------------------------

  -- завести в load_tables_status новые таблицы потока LOADER с load_type = 'X' (не грузятся до P/M);
  -- вызывается и из Load(iStream). Без имени потока не делает ничего.
  Procedure Register(iStream Varchar2);

  -- Предварительная проверка: приёмники, которые загрузит Load(iStream).
  -- Select * From Table(batch_upload_table.table_list('STREAM_REF'));
  Function table_list(iStream Varchar2) Return TLoadQueue
    Pipelined;

End batch_upload_table; -- load_obj
/
CREATE OR REPLACE Package Body batch_upload_table Is

  Type TPartitions Is Table Of Varchar2(128);

  cObject           Constant Varchar2(32) := 'BATCH_UPLOAD_TABLE'; -- объект в протоколе для всего запуска
  cMerge_Max_Rows   Constant Number := 10000000; -- до стольких строк приёмник грузится merge (M), больше - P
  cMax_Deleted_Rows Constant Number := 500000; -- merge: больше удалять нельзя - сбой источника, откат
  cMin_Source_Share Constant Number := 0.5; -- P: LOADER загрузил меньше этой доли от нашей прошлой загрузки - сбой

  p_Source_Ok   Boolean; -- все операции по текущему источнику прошли без ошибок
  p_Proc_Ok     Boolean; -- своя процедура (L) по текущему источнику отработала без ошибок
  p_Last_Rows   Pls_Integer; -- число строк, обработанных последней командой Exec
  p_First_Error Varchar2(2000); -- первая ошибка по текущему источнику - для load_tables_status
  p_All_Skipped Boolean; -- Load_Source не грузил: все приёмники пропущены по Skip_Reason

  -- таблицы групп для Make: по имени группы, внутри группы - по order_num
  Cursor cur_group_queue Is
    Select ls.group_name, ls.order_num, ls.table_name, ls.load_type, ls.state
      From load_tables_status ls
     Where ls.group_name Is Not Null
     Order By ls.group_name, ls.order_num;

  Type TGroupQueue Is Table Of cur_group_queue%Rowtype;

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

  -- Ошибка по текущему источнику: в протокол, сбросить p_Source_Ok, первую запомнить в p_First_Error
  Procedure Fail
  (
    iObject Varchar2,
    iErr    Varchar2,
    iSql    Varchar2 := Null
  ) Is
  Begin
    p_Source_Ok := False;
    If p_First_Error Is Null Then
      p_First_Error := substrb(iObject || ': ' || iErr, 1, 2000);
    End If;
    Log(iObject, 'Ошибка !', iErr || Case When iSql Is Not Null Then ' | ' || iSql End);
  End;

  -- Выполнить команду. В протокол пишется только ошибка - вместе с текстом команды;
  -- загрузка при этом не прерывается, сбрасывается p_Source_Ok.
  Procedure Exec
  (
    iObject Varchar2,
    iSql    Varchar2
  ) Is
  Begin
    Execute Immediate iSql;
    p_Last_Rows := Sql%Rowcount;
  Exception
    When Others Then
      Fail(iObject, Sqlerrm, iSql);
  End;

  ---------------------------------------------------------------- партиции
  -- партиции приёмника = пара партиций источника из loader.load_table (pkg_load имена не меняет);
  -- имя партиции = 'P' || PART_ID
  Function Dst_Partitions(iDst cur_load_queue%Rowtype) Return TPartitions Is
  Begin
    Return Set(TPartitions(iDst.src_part_1, iDst.src_part_2));
  End;

  -- список значений PART_ID для условия In (...)
  Function Part_Id_List(iParts TPartitions) Return Varchar2 Is
    p_List Varchar2(4000);
  Begin
    For i In 1 .. iParts.Count Loop
      p_List := p_List || ', ''' || substr(iParts(i), 2) || '''';
    End Loop;
    Return substr(p_List, 3);
  End;

  -- уникальный индекс приёмника для merge: PK, если есть, иначе первый по имени; Null - ключа нет
  Function Merge_Key_Index(iDst cur_load_queue%Rowtype) Return Varchar2 Is
    p_Name all_indexes.index_name%Type;
  Begin
    Select Max(i.index_name) Keep(Dense_Rank First Order By Nvl2(c.constraint_name, 0, 1), i.index_name)
      Into p_Name
      From all_indexes i, all_constraints c
     Where i.table_owner = upper(iDst.dst_owner)
       And i.table_name = upper(iDst.dst_name)
       And i.uniqueness = 'UNIQUE'
       And i.index_type Not Like 'FUNCTION-BASED%'
       And c.owner(+) = i.table_owner
       And c.index_name(+) = i.index_name
       And c.constraint_type(+) = 'P';
    Return p_Name;
  End;

  ---------------------------------------------------------------- load_tables_status
  Procedure Register(iStream Varchar2) Is
    p_Id    load_tables_status.order_num%Type;
    p_Names Varchar2(4000);
  Begin
    For r In (Select Distinct upper(lt.dtable_name) table_name
                From loader.load_table lt
               Where lt.is_remote = 'N'
                 And substr(lt.period, 1, 7) = 'STREAM_'
                 And upper(lt.period) = upper(iStream)
                 And Not Exists (Select 1
                        From load_tables_status ls
                       Where upper(lt.dtable_name) In (ls.table_name, upper(ls.src_name))))
    Loop
      Select Nvl(Max(s.order_num), 0) + 1 Into p_Id From load_tables_status s;
      Insert Into load_tables_status
        (order_num, table_name, load_type, info)
      Values
        (p_Id, r.table_name, 'X', 'Новая, заведена batch_upload_table');
      p_Names := substrb(p_Names || ', ' || r.table_name, 1, 4000);
    End Loop;
    If p_Names Is Not Null Then
      Commit;
      Log(cObject, 'Новые таблицы (X)', iStream || ': ' || substr(p_Names, 3));
    End If;
  End;

  -- Почему приёмник сейчас грузить не надо (Null - надо). Строка load_tables_status перечитывается:
  -- приёмник загружается (state = 1) - пропуск всегда. iOnly_Ready = 1 (Run, Make), приёмник P/M:
  -- пропуск и при упавшей прошлой загрузке, и если он уже загружен после LOADER. Приёмник L
  -- проверяет сама LOAD_<таблица>.MAKE (load_procedurs.init), к тому же она читает и таблицы SSWH.
  Function Skip_Reason
  (
    iDst        cur_load_queue%Rowtype,
    iOnly_Ready Number
  ) Return Varchar2 Is
    p_State load_tables_status.state%Type;
    p_End   load_tables_status.end_time%Type;
  Begin
    Select s.state, s.end_time
      Into p_State, p_End
      From load_tables_status s
     Where s.table_name = upper(iDst.dst_name);
    If p_State = 1 Then
      Return 'Загружается другим процессом';
    End If;
    If iOnly_Ready = 1 And iDst.load_type != 'L' Then
      If Nvl(p_State, 2) != 2 Then
        Return 'Прошлая загрузка завершилась с ошибкой, state = ' || p_State;
      End If;
      If p_End >= iDst.loader_end_time Then
        Return 'Уже загружена после LOADER: ' || to_char(p_End, 'dd.mm.yyyy hh24:mi:ss');
      End If;
    End If;
    Return Null;
  End;

  -- table_name = имя приёмника без владельца; строка с load_type заведена вручную
  Procedure Status_Begin(iDst cur_load_queue%Rowtype) Is
    Pragma Autonomous_Transaction;
  Begin
    Update load_tables_status s
       Set s.state = 1, s.beg_time = Sysdate, s.end_time = Null, s.info = 'Начата обработка'
     Where s.table_name = upper(iDst.dst_name);
    Commit;
  End;

  -- число строк в приёмнике после загрузки: в партиционированном - только в переключаемых партициях
  Function Count_Dst_Rows(iDst cur_load_queue%Rowtype) Return Number Is
    p_Sql Varchar2(4000) := 'Select Count(*) From ' || iDst.dst_full_name;
    p_Cnt Number;
  Begin
    If iDst.partitioned = 'YES' Then
      p_Sql := p_Sql || ' Where PART_ID In (' || Part_Id_List(Dst_Partitions(iDst)) || ')';
    End If;
    Execute Immediate p_Sql
      Into p_Cnt;
    Return p_Cnt;
  End;

  -- итог по всем приёмникам источника: p_Source_Ok - успех, число строк и тип следующей загрузки,
  -- иначе ошибка p_First_Error. iRows - сколько вставил Insert All: одно число на все приёмники P,
  -- поэтому при нескольких таких приёмниках и для приёмников M строки считаются.
  Procedure Status_End
  (
    iDst  TLoadQueue,
    iRows Number
  ) Is
    Pragma Autonomous_Transaction;
    p_P_Count   Pls_Integer := 0; -- приёмников P
    p_Rows_Now  Number;
    p_Next_Type Varchar2(1);
  Begin
    For i In 1 .. iDst.Count Loop
      If iDst(i).load_type = 'P' Then
        p_P_Count := p_P_Count + 1;
      End If;
    End Loop;
    For i In 1 .. iDst.Count Loop
      Continue When iDst(i).load_type = 'L'; -- статус ведёт своя процедура
      If p_Source_Ok Then
        If iDst(i).load_type = 'P' And p_P_Count = 1 Then
          p_Rows_Now := iRows;
        Else
          p_Rows_Now := Count_Dst_Rows(iDst(i));
        End If;
        If p_Rows_Now > cMerge_Max_Rows Then
          p_Next_Type := 'P';
        Else
          p_Next_Type := 'M';
        End If;
        If p_Next_Type != iDst(i).load_type Then
          Log(iDst(i).dst_full_name, 'Тип загрузки', iDst(i).load_type || ' -> ' || p_Next_Type || ', строк ' || p_Rows_Now);
        End If;
        Update load_tables_status s
           Set s.state = 2, s.end_time = Sysdate, s.last_success_date = Sysdate, s.loaded_rows = p_Rows_Now,
               s.info = Null, s.load_type = p_Next_Type
         Where s.table_name = upper(iDst(i).dst_name);
      Else
        Update load_tables_status s
           Set s.state = 8, s.end_time = Sysdate, s.info = p_First_Error
         Where s.table_name = upper(iDst(i).dst_name);
      End If;
    End Loop;
    Commit;
  End;

  ---------------------------------------------------------------- приёмник
  -- добавить недостающие переключаемые партиции
  Procedure Add_Missing_Partitions(iDst cur_load_queue%Rowtype) Is
    p_Parts TPartitions := Dst_Partitions(iDst);
    p_Cnt   Pls_Integer;
  Begin
    For i In 1 .. p_Parts.Count Loop
      Select Count(*)
        Into p_Cnt
        From all_tab_partitions tp
       Where tp.table_owner = upper(iDst.dst_owner)
         And tp.table_name = upper(iDst.dst_name)
         And tp.partition_name = upper(p_Parts(i));
      If p_Cnt = 0 Then
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Add Partition ' || p_Parts(i) ||
             ' Values (''' || substr(p_Parts(i), 2) || ''')');
      End If;
    End Loop;
  End;

  -- P, до вставки: очистить приёмник, отключить индексы и констрейнты
  Procedure Prepare_Dst(iDst cur_load_queue%Rowtype) Is
    p_Parts TPartitions;
  Begin
    If iDst.partitioned = 'YES' Then
      Add_Missing_Partitions(iDst);
      p_Parts := Dst_Partitions(iDst);
      For i In 1 .. p_Parts.Count Loop
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Modify Partition ' || p_Parts(i) ||
             ' Unusable Local Indexes');
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Truncate Partition ' || p_Parts(i));
      End Loop;
    Else
      -- сначала констрейнты: при отключении PK его индекс удаляется
      For cons In (Select a.constraint_name
                  From all_constraints a
                 Where a.owner = upper(iDst.dst_owner)
                   And a.table_name = upper(iDst.dst_name))
      Loop
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Disable Constraint ' || cons.constraint_name);
      End Loop;
      For idx In (Select a.owner, a.index_name
                  From all_indexes a
                 Where a.table_owner = upper(iDst.dst_owner)
                   And a.table_name = upper(iDst.dst_name))
      Loop
        Exec(iDst.dst_full_name,
             'Alter Index ' || idx.owner || '.' || idx.index_name || ' Unusable');
      End Loop;
      Exec(iDst.dst_full_name, 'Truncate Table ' || iDst.dst_full_name || ' Drop Storage');
    End If;
  End;

  -- P, после вставки: перестроить индексы, включить констрейнты
  Procedure Finish_Dst(iDst cur_load_queue%Rowtype) Is
    p_Parts TPartitions;
  Begin
    If iDst.partitioned = 'YES' Then
      p_Parts := Dst_Partitions(iDst);
      For i In 1 .. p_Parts.Count Loop
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Modify Partition ' || p_Parts(i) ||
             ' Rebuild Unusable Local Indexes');
      End Loop;
    Else
      For idx In (Select a.owner, a.index_name
                  From all_indexes a
                 Where a.table_owner = upper(iDst.dst_owner)
                   And a.table_name = upper(iDst.dst_name)
                   And a.status = 'UNUSABLE')
      Loop
        Exec(iDst.dst_full_name,
             'Alter Index ' || idx.owner || '.' || idx.index_name || ' Rebuild');
      End Loop;
      For cons In (Select a.constraint_name
                  From all_constraints a
                 Where a.owner = upper(iDst.dst_owner)
                   And a.table_name = upper(iDst.dst_name)
                   And a.status = 'DISABLED')
      Loop
        Exec(iDst.dst_full_name,
             'Alter Table ' || iDst.dst_full_name || ' Enable Constraint ' || cons.constraint_name);
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
  -- Удалено больше cMax_Deleted_Rows или больше, чем пришло из источника, - сбой источника: откат и ошибка.
  Procedure Merge_Dst
  (
    iSrc Varchar2,
    iDst cur_load_queue%Rowtype
  ) Is
    p_Index          all_indexes.index_name%Type := Merge_Key_Index(iDst);
    p_Key_Cols       Pls_Integer; -- колонок в ключе
    p_Key_Cols_Found Pls_Integer := 0; -- из них нашлось в источнике
    p_Col_List       Varchar2(32767);
    p_Src_Values     Varchar2(32767);
    p_Update_Set     Varchar2(32767);
    p_Changed_Cond   Varchar2(32767); -- условие "строка изменилась"
    p_Match_Cond     Varchar2(32767);
    p_Src_Query      Varchar2(32767);
    p_Src_Rows       Number; -- пришло строк из источника
    p_Merged_Rows    Number; -- изменено и добавлено строк (без ключа - добавлено)
    p_Deleted_Rows   Number; -- удалено строк
  Begin
    For col In (Select s.column_name,
                     dc.nullable,
                     dc.data_type,
                     (Select Count(*)
                        From all_ind_columns ic
                       Where ic.table_owner = dc.owner
                         And ic.table_name = dc.table_name
                         And ic.index_name = p_Index
                         And ic.column_name = s.column_name) is_key
                From all_tab_columns s, all_tab_columns dc
               Where s.owner = upper(iDst.src_owner)
                 And s.table_name = upper(iDst.src_name)
                 And dc.owner = upper(iDst.dst_owner)
                 And dc.table_name = upper(iDst.dst_name)
                 And dc.column_name = s.column_name
               Order By s.column_id)
    Loop
      p_Col_List := p_Col_List || ', ' || col.column_name;
      p_Src_Values := p_Src_Values || ', s.' || col.column_name;
      If col.column_name = 'PART_ID' Then
        p_Key_Cols_Found := p_Key_Cols_Found + Sign(col.is_key);
      Elsif col.is_key > 0 Then
        p_Key_Cols_Found := p_Key_Cols_Found + 1;
        If col.nullable = 'Y' Then
          p_Match_Cond := p_Match_Cond || ' And (t.' || col.column_name || ' = s.' || col.column_name ||
                  ' Or t.' || col.column_name || ' Is Null And s.' || col.column_name || ' Is Null)';
        Else
          p_Match_Cond := p_Match_Cond || ' And t.' || col.column_name || ' = s.' || col.column_name;
        End If;
      Else
        p_Update_Set := p_Update_Set || ', t.' || col.column_name || ' = s.' || col.column_name;
        If col.data_type In ('CLOB', 'NCLOB', 'BLOB') Then
          -- Decode с LOB не работает
          p_Changed_Cond := p_Changed_Cond || ' Or Nvl(dbms_lob.compare(t.' || col.column_name || ', s.' || col.column_name ||
                    '), 1) != 0 And (t.' || col.column_name || ' Is Not Null Or s.' || col.column_name || ' Is Not Null)';
        Else
          p_Changed_Cond := p_Changed_Cond || ' Or Decode(t.' || col.column_name || ', s.' || col.column_name || ', 0, 1) = 1';
        End If;
      End If;
    End Loop;
    Select Count(*)
      Into p_Key_Cols
      From all_ind_columns ic
     Where ic.table_owner = upper(iDst.dst_owner)
       And ic.table_name = upper(iDst.dst_name)
       And ic.index_name = p_Index;
    If p_Key_Cols_Found < p_Key_Cols Then
      Fail(iDst.dst_full_name, 'Merge невозможен: не все колонки ключа ' || p_Index || ' есть в источнике ' || iSrc);
      Return;
    End If;
    p_Match_Cond := substr(p_Match_Cond, 6);
    If p_Match_Cond Is Null Then
      p_Index := Null; -- ключ из одного PART_ID - сверка по всем колонкам
    End If;
    p_Src_Query := '(Select ' || substr(p_Col_List, 3) || ' From ' || iSrc;
    If iDst.partitioned = 'YES' Then
      p_Src_Query := p_Src_Query || ' Where PART_ID In (' || Part_Id_List(Dst_Partitions(iDst)) || ')';
    End If;
    p_Src_Query := p_Src_Query || ')';
    Execute Immediate 'Select Count(*) From ' || p_Src_Query
      Into p_Src_Rows;
    If p_Index Is Null Then
      p_Match_Cond := 'Not (' || substr(p_Changed_Cond, 5) || ')'; -- строки совпадают по всем колонкам
    End If;
    -- 1. удалить строки, которых нет в источнике
    p_Last_Rows := Null;
    Exec(iDst.dst_full_name,
         'Delete From ' || iDst.dst_full_name || ' t' || chr(10) ||
         'Where Not Exists (Select 1 From ' || p_Src_Query || ' s Where ' || p_Match_Cond || ')' ||
         Case When iDst.partitioned = 'YES' Then chr(10) || 'And t.PART_ID In (' || Part_Id_List(Dst_Partitions(iDst)) || ')' End);
    If p_Last_Rows Is Null Then
      Rollback;
      Return;
    End If;
    p_Deleted_Rows := p_Last_Rows;
    -- 2. с ключом - merge, без ключа - добавить строки источника, которых нет в приёмнике
    p_Last_Rows := Null;
    If p_Index Is Not Null Then
      Exec(iDst.dst_full_name,
           'Merge Into ' || iDst.dst_full_name || ' t' || chr(10) || 'Using ' || p_Src_Query || ' s' || chr(10) ||
           'On (' || p_Match_Cond || ')' || chr(10) ||
           Case When p_Update_Set Is Not Null Then
             'When Matched Then Update Set ' || substr(p_Update_Set, 3) || chr(10) || ' Where ' || substr(p_Changed_Cond, 5) || chr(10)
           End ||
           'When Not Matched Then Insert (' || substr(p_Col_List, 3) || ') Values (' || substr(p_Src_Values, 3) || ')');
    Else
      Exec(iDst.dst_full_name,
           'Insert Into ' || iDst.dst_full_name || ' (' || substr(p_Col_List, 3) || ')' || chr(10) ||
           'Select ' || substr(p_Src_Values, 3) || ' From ' || p_Src_Query || ' s' || chr(10) ||
           'Where Not Exists (Select 1 From ' || iDst.dst_full_name || ' t Where ' || p_Match_Cond || ')');
    End If;
    If p_Last_Rows Is Null Then
      Rollback;
      Return;
    End If;
    p_Merged_Rows := p_Last_Rows;
    If p_Deleted_Rows > cMax_Deleted_Rows Or p_Deleted_Rows > p_Src_Rows Then
      Rollback;
      Fail(iDst.dst_full_name, 'Удаляется ' || p_Deleted_Rows || ' строк при ' || p_Src_Rows || ' пришедших (предел ' || cMax_Deleted_Rows ||
           '): похоже на сбой источника ' || iSrc || ', merge отменён');
      Return;
    End If;
    Commit;
    Log(iDst.dst_full_name, 'Merge завершён',
        'Пришло ' || p_Src_Rows || Case When p_Index Is Null Then ', сверка по всем колонкам: добавлено '
                                  Else ', по ключу ' || p_Index || ': изменено и добавлено ' End ||
        p_Merged_Rows || ', удалено ' || p_Deleted_Rows);
  Exception
    When Others Then
      Rollback;
      Fail(iDst.dst_full_name, Sqlerrm);
  End;

  -- L: своя процедура LOAD_<таблица>.MAKE. Ошибки она обрабатывает и пишет в load_tables_status сама,
  -- поэтому на p_Source_Ok и на статус приёмников P/M того же источника не влияет.
  Procedure Call_Own_Proc(iDst cur_load_queue%Rowtype) Is
    p_State load_tables_status.state%Type;
  Begin
    Log(iDst.dst_full_name, 'Своя процедура', iDst.load_proc);
    Execute Immediate 'Begin ' || iDst.load_proc || '; End;';
    Select s.state Into p_State From load_tables_status s Where s.table_name = upper(iDst.dst_name);
    If p_State != 2 Then
      p_Proc_Ok := False;
      Log(iDst.dst_full_name, 'Своя процедура завершилась с ошибкой', 'state = ' || p_State);
    End If;
  Exception
    When Others Then
      p_Proc_Ok := False;
      Log(iDst.dst_full_name, 'Ошибка !', Sqlerrm || ' | ' || iDst.load_proc);
  End;

  ---------------------------------------------------------------- источник
  -- Insert All: по ветке When на каждый приёмник (партиционированный - только его партиции),
  -- вставляются общие колонки
  Function Insert_Sql
  (
    iSrc Varchar2,
    iDst TLoadQueue
  ) Return Varchar2 Is
    p_Sql             Varchar2(32767);
    p_Cols            Varchar2(32767);
    p_Parts           TPartitions;
    p_Union_Parts     TPartitions := TPartitions();
    p_All_Partitioned Boolean := True; -- все приёмники партиционированы
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
      If iDst(i).partitioned = 'YES' Then
        -- в партиционированный приёмник - только строки его партиций
        p_Parts    := Dst_Partitions(iDst(i));
        p_Sql      := p_Sql || chr(10) || 'When PART_ID In (' || Part_Id_List(p_Parts) || ')';
        p_Union_Parts := p_Union_Parts Multiset Union Distinct p_Parts;
      Else
        p_Sql     := p_Sql || chr(10) || 'When 1 = 1';
        p_All_Partitioned := False;
      End If;
      p_Sql := p_Sql || ' Then Into ' || iDst(i).dst_full_name || chr(10) || ' (' || p_Cols || ')' ||
               chr(10) || ' Values' || chr(10) || ' (' || p_Cols || ')';
    End Loop;
    p_Sql := 'Insert /*+APPEND*/ All' || p_Sql || chr(10) || 'Select * From ' || iSrc;
    If p_All_Partitioned Then
      -- все приёмники партиционированы - читаем из источника только нужные партиции
      p_Sql := p_Sql || chr(10) || 'Where PART_ID In (' || Part_Id_List(p_Union_Parts) || ')';
    End If;
    Return p_Sql;
  End;

  -- iOnly_Ready = 1 - загрузка по готовности (Run, Make), см. Skip_Reason
  Procedure Load_Source
  (
    iSrc        Varchar2,
    iDst        TLoadQueue,
    iOnly_Ready Number
  ) Is
    p_To_Load       TLoadQueue := TLoadQueue(); -- приёмники, которые надо грузить
    p_P_Targets     TLoadQueue := TLoadQueue(); -- приёмники P - для Insert All
    p_Names         Varchar2(4000);
    p_Skip_Why      Varchar2(200);
    p_Inserted_Rows Number; -- вставлено строк во все приёмники P
    -- объект в протоколе: приёмник, а если их у источника несколько - источник
    p_Log_Object Varchar2(261) := Case When iDst.Count = 1 Then iDst(1).dst_full_name Else iSrc End;
  Begin
    p_Source_Ok  := True;
    p_Proc_Ok := True;
    p_First_Error  := Null;
    p_All_Skipped := False;
    For i In 1 .. iDst.Count Loop
      p_Skip_Why := Skip_Reason(iDst(i), iOnly_Ready);
      If p_Skip_Why Is Null Then
        p_To_Load.Extend;
        p_To_Load(p_To_Load.Count) := iDst(i);
      Else
        Log(iDst(i).dst_full_name, 'Пропущена', p_Skip_Why);
      End If;
    End Loop;
    If p_To_Load.Count = 0 Then
      p_All_Skipped := True;
      Return;
    End If;
    Log(p_Log_Object, 'Начало загрузки', 'Из ' || iSrc);
    -- 0. P: источник подозрительно мал по сравнению с прошлой загрузкой - приёмники не трогаем
    For i In 1 .. p_To_Load.Count Loop
      If p_To_Load(i).load_type = 'P' And p_To_Load(i).dst_rows > 0 And
         Nvl(p_To_Load(i).loader_rows, 0) < p_To_Load(i).dst_rows * cMin_Source_Share Then
        Fail(p_Log_Object, 'Источник подозрительно мал: LOADER загрузил ' || Nvl(p_To_Load(i).loader_rows, 0) || ', в ' ||
             p_To_Load(i).dst_full_name || ' было ' || p_To_Load(i).dst_rows || ' (порог ' || cMin_Source_Share * 100 || '%)');
      End If;
    End Loop;
    If Not p_Source_Ok Then
      Log(p_Log_Object, 'Загрузка отменена');
      Status_End(p_To_Load, Null);
      Return;
    End If;
    -- 1. подготовить приёмники: P - очистить, M - только добавить партиции, L - ничего
    For i In 1 .. p_To_Load.Count Loop
      If p_To_Load(i).load_type != 'L' Then
        Status_Begin(p_To_Load(i));
      End If;
      If p_To_Load(i).load_type = 'P' Then
        Prepare_Dst(p_To_Load(i));
        p_P_Targets.Extend;
        p_P_Targets(p_P_Targets.Count) := p_To_Load(i);
      Elsif p_To_Load(i).load_type = 'M' And p_To_Load(i).partitioned = 'YES' Then
        Add_Missing_Partitions(p_To_Load(i));
      End If;
      p_Names := p_Names || ', ' || Case When p_To_Load.Count > 1 Then p_To_Load(i).dst_full_name || ' ' End ||
                 '(' || p_To_Load(i).load_type || ')';
    End Loop;
    Log(p_Log_Object, 'Приёмники подготовлены', substr(p_Names, 3));
    If p_P_Targets.Count > 0 Then
      -- 2. P: одна вставка во все такие приёмники
      Begin
        p_Last_Rows := Null;
        Exec(p_Log_Object, Insert_Sql(iSrc, p_P_Targets));
        Commit;
        p_Inserted_Rows := p_Last_Rows;
        If p_Inserted_Rows Is Not Null Then
          Log(p_Log_Object, 'Вставка завершена', 'Загружено ' || p_Inserted_Rows || ' записей');
        End If;
      Exception
        When Others Then
          -- ошибка при сборке команды (выполнение ловит Exec)
          Fail(p_Log_Object, Sqlerrm);
      End;
      -- 3. P: вернуть индексы и констрейнты
      For i In 1 .. p_P_Targets.Count Loop
        Finish_Dst(p_P_Targets(i));
      End Loop;
    End If;
    -- 4. M: merge в каждый такой приёмник, L: своя процедура
    For i In 1 .. p_To_Load.Count Loop
      If p_To_Load(i).load_type = 'M' Then
        Merge_Dst(iSrc, p_To_Load(i));
      Elsif p_To_Load(i).load_type = 'L' Then
        Call_Own_Proc(p_To_Load(i));
      End If;
    End Loop;
    -- 5. итог
    If p_Source_Ok And p_Proc_Ok Then
      Log(p_Log_Object, 'Загрузка завершена');
    Else
      Log(p_Log_Object, 'Загрузка завершена с ошибками');
    End If;
    Status_End(p_To_Load, p_Inserted_Rows);
  Exception
    When Others Then
      Fail(p_Log_Object, Sqlerrm);
      Status_End(p_To_Load, p_Inserted_Rows);
  End;

  ---------------------------------------------------------------- точка входа
  Procedure Do_Load
  (
    iStream     Varchar2,
    iDst_Name   Varchar2,
    iOnly_Ready Number
  ) Is
    p_All_Targets    TLoadQueue; -- все приёмники, упорядочены по источнику
    p_Dst            TLoadQueue := TLoadQueue(); -- приёмники текущего источника
    p_Sources        Pls_Integer := 0; -- обработано источников
    p_Failed_Sources Pls_Integer := 0; -- из них с ошибками
  Begin
    If iOnly_Ready = 0 Then
      Register(iStream);
    End If;
    Open cur_load_queue(iStream, iDst_Name, iOnly_Ready);
    Fetch cur_load_queue Bulk Collect
      Into p_All_Targets;
    Close cur_load_queue;
    If iOnly_Ready = 1 And p_All_Targets.Count = 0 Then
      Return; -- джобу нечего грузить
    End If;
    Log(cObject, 'Начало загрузки',
        Case When iOnly_Ready = 1 Then 'Run ' End || 'Stream=' || iStream ||
        Case When iDst_Name Is Not Null Then ', Dst=' || iDst_Name End);
    For i In 1 .. p_All_Targets.Count Loop
      p_Dst.Extend;
      p_Dst(p_Dst.Count) := p_All_Targets(i);
      -- последний приёмник источника - загружаем источник
      If i = p_All_Targets.Count Or p_All_Targets(i + 1).src_full_name != p_All_Targets(i).src_full_name Then
        dbms_application_info.set_client_info('Loading ' || p_All_Targets(i).src_full_name);
        Load_Source(p_All_Targets(i).src_full_name, p_Dst, iOnly_Ready);
        p_Dst := TLoadQueue();
        p_Sources := p_Sources + 1;
        If Not p_Source_Ok Or Not p_Proc_Ok Then
          p_Failed_Sources := p_Failed_Sources + 1;
        End If;
      End If;
    End Loop;
    Log(cObject, 'Загрузка завершена', 'Источников: ' || p_Sources || ', с ошибками: ' || p_Failed_Sources);
  Exception
    When Others Then
      -- курсор уровня пакета остаётся открытым до конца сессии
      If cur_load_queue%Isopen Then
        Close cur_load_queue;
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

  ---------------------------------------------------------------- группы
  -- группа готова: первая таблица готова по правилу Run, у всех таблиц прошлая загрузка успешна
  Function Group_Ready
  (
    iGrp   TGroupQueue,
    iFirst Pls_Integer,
    iLast  Pls_Integer
  ) Return Boolean Is
  Begin
    For i In iFirst .. iLast Loop
      If Nvl(iGrp(i).state, 2) != 2 Then
        Return False;
      End If;
    End Loop;
    For r In cur_load_queue(Null, Null, 1, iGrp(iFirst).table_name) Loop
      Return True;
    End Loop;
    Return False;
  End;

  -- загрузить одну таблицу группы: с источником в LOADER - как обычно, без него - своей процедурой
  Procedure Load_Member(iTable Varchar2) Is
    p_Dst        TLoadQueue;
    p_Has_Source Pls_Integer; -- у таблицы есть источник в потоке LOADER
    p_Has_Proc   Pls_Integer; -- есть LOAD_<таблица>.MAKE
    p_Proc_Dst   cur_load_queue%Rowtype;
  Begin
    Open cur_load_queue(Null, Null, 0, iTable);
    Fetch cur_load_queue Bulk Collect
      Into p_Dst;
    Close cur_load_queue;
    If p_Dst.Count > 0 Then
      -- одна строка: у источника может быть по строке на каждый поток LOADER.
      -- По готовности: таблица, уже загруженная после LOADER (например, своим джобом), пропускается
      Load_Source(p_Dst(1).src_full_name, TLoadQueue(p_Dst(1)), 1);
      Return;
    End If;
    p_Source_Ok   := True;
    p_Proc_Ok  := True;
    p_First_Error  := Null;
    p_All_Skipped := False;
    Select Count(*)
      Into p_Has_Source
      From load_tables_status ls, loader.load_table lt
     Where ls.table_name = upper(iTable)
       And upper(lt.dtable_name) = Nvl(upper(ls.src_name), ls.table_name)
       And lt.is_remote = 'N'
       And substr(lt.period, 1, 7) = 'STREAM_';
    Select Count(*)
      Into p_Has_Proc
      From all_procedures pr
     Where pr.owner = User
       And pr.object_name = 'LOAD_' || upper(iTable)
       And pr.procedure_name = 'MAKE';
    If p_Has_Source = 0 And p_Has_Proc > 0 Then
      p_Proc_Dst.dst_name      := upper(iTable);
      p_Proc_Dst.dst_full_name := User || '.' || upper(iTable);
      p_Proc_Dst.load_type     := 'L';
      p_Proc_Dst.load_proc     := User || '.LOAD_' || upper(iTable) || '.MAKE';
      Call_Own_Proc(p_Proc_Dst);
    Else
      p_Proc_Ok := False;
      Log(User || '.' || upper(iTable), 'Ошибка !',
          'Таблицу группы нельзя загрузить: источник в LOADER не загружен успешно, load_type = X ' ||
          'или нет LOAD_' || upper(iTable) || '.MAKE');
    End If;
  End;

  Procedure Make Is
    p_Tables        TGroupQueue;
    p_Group_First   Pls_Integer := 1; -- первая таблица текущей группы
    p_Group_Last    Pls_Integer; -- последняя таблица текущей группы
    p_Groups        Pls_Integer := 0; -- загружено групп
    p_Failed_Groups Pls_Integer := 0; -- из них остановлено на ошибке
  Begin
    Open cur_group_queue;
    Fetch cur_group_queue Bulk Collect
      Into p_Tables;
    Close cur_group_queue;
    While p_Group_First <= p_Tables.Count Loop
      p_Group_Last := p_Group_First;
      While p_Group_Last < p_Tables.Count And p_Tables(p_Group_Last + 1).group_name = p_Tables(p_Group_First).group_name Loop
        p_Group_Last := p_Group_Last + 1;
      End Loop;
      If Group_Ready(p_Tables, p_Group_First, p_Group_Last) Then
        If p_Groups = 0 Then
          Log(cObject, 'Начало загрузки', 'Make');
        End If;
        p_Groups := p_Groups + 1;
        Log(cObject, 'Группа ' || p_Tables(p_Group_First).group_name, 'Таблиц: ' || (p_Group_Last - p_Group_First + 1));
        For i In p_Group_First .. p_Group_Last Loop
          dbms_application_info.set_client_info('Group ' || p_Tables(i).group_name || ': ' || p_Tables(i).table_name);
          Load_Member(p_Tables(i).table_name);
          -- первая таблица пропущена (её грузит другой процесс или уже загрузил) - не грузим всю группу
          If i = p_Group_First And p_All_Skipped Then
            Log(cObject, 'Группа ' || p_Tables(p_Group_First).group_name || ' пропущена',
                'Пропущена первая таблица ' || p_Tables(i).table_name);
            Exit;
          End If;
          If Not p_Source_Ok Or Not p_Proc_Ok Then
            p_Failed_Groups := p_Failed_Groups + 1;
            Log(cObject, 'Группа ' || p_Tables(p_Group_First).group_name || ' остановлена', 'На ' || p_Tables(i).table_name);
            Exit;
          End If;
        End Loop;
      End If;
      p_Group_First := p_Group_Last + 1;
    End Loop;
    If p_Groups > 0 Then
      Log(cObject, 'Загрузка завершена', 'Групп: ' || p_Groups || ', остановлено на ошибке: ' || p_Failed_Groups);
    End If;
  Exception
    When Others Then
      If cur_group_queue%Isopen Then
        Close cur_group_queue;
      End If;
      If cur_load_queue%Isopen Then
        Close cur_load_queue;
      End If;
      Log(cObject, 'Ошибка !', Sqlerrm);
      Raise;
  End;

  Function table_list(iStream Varchar2) Return TLoadQueue
    Pipelined Is
  Begin
    For r In cur_load_queue(iStream, Null) Loop
      Pipe Row(r);
    End Loop;
    Return;
  End;

End batch_upload_table;
/
