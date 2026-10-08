create or replace package load_pnap_act_prt is

  -- Author  : ГУСЕЙНОВ_Ш
  -- Created : 09.03.2023 17:19:31
  -- Purpose : Загрузка PNAP_ACT_PRT с фильтрацией

  PROCEDURE MAKE;

end load_pnap_act_prt;
/
create or replace package body load_pnap_act_prt is

  reload_from     date;
  status        pls_integer default 0;
  cnt_rows        pls_integer default 0;

  v_table_name    varchar2(32) default 'PNAP_ACT_PRT_2';

  procedure log(iaction in varchar2, imsg in nvarchar2 default '')
  is
  PRAGMA AUTONOMOUS_TRANSACTION;
  begin
    insert into log_load_tables values(CURRENT_TIMESTAMP, v_table_name, iaction, imsg);
    commit;
  end log;

  procedure remove_extra_records
  is
  begin
    dbms_application_info.set_module('RM EXTRA '||v_table_name, 'FROM '||to_char(reload_from, 'dd.mm.yyyy'));
    log('Очистка', 'Start');

    delete from sswh.pnap_act_prt_2 prt
    where (
        actp_id, act_month
    ) in
    (
      select actp_id, act_month
      from (
        select /*+ parallel(4)*/
            actp_id, act_month, pncd_id, rfbn_id, emp_id, riac_id,
            source_id, act_date, notes, in_date, ip_pc
        from sswh.pnap_act_prt_2 prt
        where prt.act_month>=reload_from and prt.act_month<last_day(sysdate)
        minus
        select /*+ parallel(4)*/
            actp_id, act_month, pncd_id, rfbn_id, emp_id, riac_id,
            source_id, act_date, notes, in_date, ip_pc
        from loader.pnap_act_prt prt
        where prt.act_month>=reload_from and prt.act_month<last_day(sysdate)
        and   prt.riac_id In (100, 120, 121, 110, 122, 150, 151, 152)

      )
    );
    cnt_rows:=sql%Rowcount;
    
    if cnt_rows>500000 then 
       log('Ошибка !', 'К удалению '||cnt_rows||' записей');
       raise_application_error(-20100, 'Ошибка! К удалению более 500 тыс. записей');
       
       return;
    else
       commit;
       log('Удаление завершено', 'Удалено '||cnt_rows||' записей');
    end if;    
  end remove_extra_records;

  procedure insert_new_records
  is
  begin
    dbms_application_info.set_module('Загрузка '||v_table_name, 'FROM '||to_char(reload_from, 'dd.mm.yyyy'));
    log('Начало загрузки');

    insert into sswh.pnap_act_prt_2(
        actp_id, act_month, pncd_id, rfbn_id, emp_id, riac_id,
        source_id, act_date, notes, in_date, ip_pc
    )
    select /*+ parallel(4)*/
        actp_id, act_month, pncd_id, rfbn_id, emp_id, riac_id,
        source_id, act_date, notes, in_date, ip_pc
    from loader.pnap_act_prt prt
    where prt.act_month>=reload_from and prt.act_month<last_day(sysdate)
    and   prt.riac_id In (100, 120, 121, 110, 122, 150, 151, 152)
    minus
    select /*+ parallel(4)*/
        actp_id, act_month, pncd_id, rfbn_id, emp_id, riac_id,
        source_id, act_date, notes, in_date, ip_pc
    from sswh.pnap_act_prt_2 prt
    where prt.act_month>=reload_from and prt.act_month<last_day(sysdate);

    cnt_rows:=sql%Rowcount;
    commit;
    log('Загрузка завершена', 'Загружено  '||cnt_rows||' записей');

  end insert_new_records;


  procedure make
  is
  begin
    log('Начало загрузки');
    load_procedurs.init(v_table_name, reload_from, status);
    if status=0 then return; end if;
    --

    remove_extra_records;
    insert_new_records;
    --
    
    load_procedurs.stop(v_table_name, cnt_rows);
    load_procedurs.shrink_table(v_table_name, 'N');

    log( 'MAKE FINISH');

    exception when others then
      begin
        dbms_application_info.set_module(v_table_name, 'LOADING FAULT');
        load_procedurs.fault(v_table_name);
      end;
  end make;

begin
  execute immediate 'alter session set sort_area_size=50000000';
  execute immediate 'alter session set sort_area_retained_size=50000000';
end load_pnap_act_prt;
/
