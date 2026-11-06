-- batch_upload_table: Make по одной группе. Три правки, остальное без изменений.

---------------------------------------------------------------- 1. Спецификация: вместо "Procedure Make;"
  -- iGroup_Name - имя группы (load_tables_status.group_name), регистр не важен;
  -- Null - все группы с ежедневной загрузкой (load_tables_status.freg = 'D') по порядку
  Procedure Make(iGroup_Name Varchar2 := Null);

---------------------------------------------------------------- 2. Тело: курсор cur_group_queue целиком
  -- таблицы групп для Make: по имени группы, внутри группы - по order_num;
  -- iGroup_Name = Null - все группы с freg = 'D', иначе только эта группа (freg не важен)
  Cursor cur_group_queue(iGroup_Name Varchar2) Is
    Select ls.group_name, ls.order_num, ls.table_name, ls.load_type, ls.state
      From load_tables_status ls
     Where ls.group_name Is Not Null
       And (iGroup_Name Is Null And ls.freg = 'D' Or upper(ls.group_name) = upper(iGroup_Name))
     Order By ls.group_name, ls.order_num;

---------------------------------------------------------------- 3. Тело Make: заголовок, Open и первый Log
  Procedure Make(iGroup_Name Varchar2 := Null) Is
  ...
  Begin
    Open cur_group_queue(iGroup_Name);
  ...
        If p_Groups = 0 Then
          Log(cObject, 'Начало загрузки', 'Make' || Case When iGroup_Name Is Not Null Then ' Group=' || iGroup_Name End);
        End If;
