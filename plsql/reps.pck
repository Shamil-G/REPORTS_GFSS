create or replace package reps is

  -- Author  : ГУСЕЙНОВ_Ш
  -- Created : 02.06.2023 14:32:39
  -- Purpose : Manage reports
  
  -- Public function and procedure declarations
  procedure remove_report(idate_report in varchar2, inum_report in pls_integer);

  function add_report(iname in varchar2, idate_first in varchar2, idate_second in varchar2, irfpm_id in varchar2, 
            irfbn_id in varchar2, ilive_time in number, ifile_path in varchar2) return pls_integer;

end reps;
/
create or replace package body reps is
  
  procedure remove_report(idate_report in varchar2, inum_report in pls_integer)
  is
  begin
    delete from load_report_status st
    where to_char(st.date_execute,'YYYY-MM-DD') = idate_report
    and   st.num = inum_report;
    commit;
  end remove_report;

  function add_report(iname in varchar2, idate_first in varchar2, idate_second in varchar2, irfpm_id in varchar2, 
            irfbn_id in varchar2, ilive_time in number, ifile_path in varchar2) return pls_integer
  is
    v_count pls_integer default 1;
    v_num   pls_integer default 0;
    v_rec   LOAD_REPORT_STATUS%rowtype;
  begin
      select coalesce(max(num),0)+1 into v_num from LOAD_REPORT_STATUS st
      where trunc(st.date_execute,'DD') = trunc(sysdate,'DD');
      -- Check exist file
      select count(ifile_path) into v_count from LOAD_REPORT_STATUS st where st.file_path = ifile_path;
      util.log('REPS', 'ADD REPORT', 'iname: '||iname||', live_time: '||ilive_time||', v_num: '||v_num||', v_count: '||v_count);
      -- Если отчета нет - то занесем информацию о его создании
      if v_count = 0 then
         util.log('REPS', 'ADD REPORT. ADD REPORT', 'iname: '||iname||', live_time: '||ilive_time||', v_num: '||v_num||', v_count: '||v_count);
        insert into LOAD_REPORT_STATUS(date_execute, num, name, date_first, DATE_SECOND, RFPM_ID, RFBN_ID, status, live_time, file_path)  
               values(sysdate, v_num, iname, idate_first, iDATE_SECOND, iRFPM_ID, iRFBN_ID, 1, ilive_time, ifile_path);
        commit;
        return 0;
      end if;
      
      select t.* into v_rec from (select * from LOAD_REPORT_STATUS st where st.file_path = ifile_path order by st.date_execute) t where rownum=1;

      -- Если отчет был запущен не в текущий день и он незавершен, то удалим его и создадим новый
      if v_rec.status = '1' and trunc(v_rec.date_execute,'DD') != trunc(sysdate,'DD')
      then
         util.log('REPS', 'ADD REPORT. REMOVE INCOMPLETED REPORT', 'iname: '||iname||', live_time: '||ilive_time||', v_num: '||v_num||', v_count: '||v_count||', STATUS: '||v_rec.status);
         delete from LOAD_REPORT_STATUS st where st.file_path = ifile_path;
         util.log('REPS', 'ADD REPORT. ADD REPORT', 'iname: '||iname||', live_time: '||ilive_time||', v_num: '||v_num||', v_count: '||v_count||', STATUS: '||v_rec.status);
         insert into LOAD_REPORT_STATUS(date_execute, num, name, date_first, DATE_SECOND, RFPM_ID, RFBN_ID, status, live_time, file_path)  
                values(sysdate, v_num, iname, idate_first, iDATE_SECOND, iRFPM_ID, iRFBN_ID, 1, ilive_time, ifile_path);
         commit;
         return 0;
      end if;
      
      util.log('REPS', 'ADD REPORT. REPORT READY OR RUNNING NOW', 'iname: '||iname||', live_time: '||ilive_time||', v_num: '||v_num||', v_count: '||v_count||', STATUS: '||v_rec.status);
      return v_rec.status;

  end add_report;

begin
  null;
end reps;
/
