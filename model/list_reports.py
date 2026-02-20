from app_config import REPORT_MODULE_PATH

# live_time - время жизни отчета в часах, может указываться с 2 знаками после запятой
# в этом случае минимальное время жизни отчета составляет 36 секунд


dict_reports = {
    "ДИА": 
    [
        {
            "grp_name": "1501", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1501",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Количество иждивенцев и сумма 0701 за период",
                    "num_rep": "01",
                    "proc": "rep_0701_01",
                    "data_approve": "13.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Списочный состав иждивенцев",
                    "num_rep": "02",
                    "proc": "rep_0701_02",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Списочный состав получателей 0701, с ребенком до 3 лет",
                    "num_rep": "03",
                    "proc": "rep_0701_03",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Списочный состав получателей 0701, с иждивенцем старше 18 лет",
                    "num_rep": "04",
                    "proc": "rep_0701_04",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по "},
                },
                {
                    "name": "Списки умерших кормильцев по действующим СВ",
                    "num_rep": "05",
                    "proc": "rep_0701_05",
                    "data_approve": "27.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по "},
                }
            ]
        },
        {
            "grp_name": "1502", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1502",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Получатели СВут 0702 за месяц",
                    "num_rep": "01",
                    "proc": "rep_0702_01",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "На"},
                },
                {
                    "name": "Получатели СВут 0702 за период",
                    "num_rep": "02",
                    "proc": "rep_0702_02",
                    "data_approve": "21.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Получатели СВут 0702 за период c 1 разделом",
                    "num_rep": "03",
                    "proc": "rep_0702_03",
                    "data_approve": "20.01.2026",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},

                    "meta_params": {
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                }
            ]
        },
        {
            "grp_name": "1503", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1503",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "СО после окончания СВпр, в градации по месяцам после даты окончания выплаты",
                    "num_rep": "01",
                    "proc": "rep_0703_01",
                    "data_approve": "22.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "На"},
                },
                {
                    "name": "Получатели СВпр, выплата которым назначена в тот же месяц, что и месяц окончания СВпр",
                    "num_rep": "02",
                    "proc": "rep_0703_02",
                    "data_approve": "23.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Выберите месяц: "},
                },
                {
                    "name": "Получатели СВпр за период",
                    "num_rep": "03",
                    "proc": "rep_0703_03",
                    "data_approve": "22.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                }
            ]
        },
        {
            "grp_name": "1504", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1504",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Получатели СВбр и СВур, у которых между датами назначения есть СВпр",
                    "num_rep": "01",
                    "proc": "rep_0704_01",
                    "data_approve": "30.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Получатели СВбр",
                    "num_rep": "02",
                    "proc": "rep_0704_02",
                    "data_approve": "21.12.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Получатели СВбр за период с СО между датой риска и датой окончания",
                    "num_rep": "03",
                    "proc": "rep_0704_03",
                    "data_approve": "18.10.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Получатели СВбр за период с количеством месяцев участия СО",
                    "num_rep": "04",
                    "proc": "rep_0704_04",
                    "data_approve": "28.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
                {
                    "name": "Получатели СВбр с назначенными выплатами более 3 млн.",
                    "num_rep": "05",
                    "proc": "rep_0704_05",
                    "data_approve": "24.04.2025",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Выберите начальную дату:"},
                },
                
            ]
        },
        {
            "grp_name": "1505", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1505",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Получатели СВур",
                    "num_rep": "01",
                    "proc": "rep_0705_01",
                    "data_approve": "30.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "C", "date_second": "по"},
                },
            ]
        },
        { 
            "grp_name": "300", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.300",
            "live_time": "0",
            "list": 
            [
                {
                "name": "Сведения о поступивших возвратах излишне зачисленных (выплаченных) сумм социальных выплат. Отчет 9V для Министерства",
                "num_rep": "01",
                "proc": "rep_dia_300_09",
                "data_approve": "13.06.2023",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                {
                    "name": "Список плательщиков, уплативших социальные отчисления за работников с численностью более 50 человек хотя бы 1 раз за предыдущие 6 месяцев",
                    "num_rep": "02",
                    "proc": "rep_dia_50",
                    "data_approve": "26.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            ]
        },
        { 
            "grp_name": "3000", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3000",
            "live_time": "0",
            "list": 
            [
                {
                "name": "СО по категориям МЗП и регионам (3029)",
                "num_rep": "01",
                "proc": "rep_dia_3029",
                "data_approve": "14.03.2025",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                {
                "name": "Стаж участия в СОСС (3023)",
                "num_rep": "02",
                "proc": "rep_dia_3023",
                "data_approve": "12.03.2025",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                {
                "name": "СО по категориям МЗП и районам (3029-районы)",
                "num_rep": "03",
                "proc": "rep_dia_3029_1",
                "data_approve": "14.03.2025",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по "},
                },
            ]
        },

        { 
            "grp_name": "6020", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.6020",
            "live_time": "0",
            "list": 
            [
                {
                "name": "Список лиц, которым назначена социальная выплата на случай потери кормильца",
                "num_rep": "01",
                "proc": "rep_dia_6021",
                "data_approve": "14.09.2023",
                "author": "Алиманов Д.Д.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                {
                "name": "Список лиц, которым назначена социальная выплата на случай утраты трудоспособности",
                "num_rep": "02",
                "proc": "rep_dia_6022",
                "data_approve": "14.09.2023",
                "author": "Алиманов Д.Д.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                 {
                "name": "Список лиц, которым назначена социальная выплата на случай потери работы",
                "num_rep": "03",
                "proc": "rep_dia_6023",
                "data_approve": "14.09.2023",
                "author": "Алиманов Д.Д.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                 {
                "name": "Список лиц, которым назначена социальная выплата на случай потери дохода в связи с беременностью и родами, усыновлением/удочерением ребенка",
                "num_rep": "04",
                "proc": "rep_dia_6024",
                "data_approve": "14.09.2023",
                "author": "Алиманов Д.Д.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                 {
                "name": "Список лиц, которым назначена социальная выплата 0704 и которые платили сами за себя",
                "num_rep": "05",
                "proc": "rep_dia_6024_1",
                "data_approve": "14.09.2023",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по "},
                },
                 {
                "name": "Список лиц, которым назначена социальная выплата на случай потери дохода в связи с уходом за ребенком по достижении им возраста 1 года",
                "num_rep": "06",
                "proc": "rep_dia_6025",
                "data_approve": "14.09.2023",
                "author": "Алиманов Д.Д.",
                "params": {"date_first": "C", "date_second": "по "},
                }

            ]
        },
        {
            "grp_name": "ЕдПлатеж", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.cp",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Сведения о численности участников и сумм их СО",
                    "num_rep": "01",
                    "proc": "rep_dia_cp_01",
                    "data_approve": "12.07.2023",
                    "author": "Адильханова А.К.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                "name": "Участники ЕП, в разрезе пола и возраста",
                "num_rep": "02",
                "proc": "rep_dia_cp_02",
                "data_approve": "10.06.2023",
                "author": "Адильханова А.К.",
                "params": {"date_first": "C", "date_second": "по", "srfbn_id": "Код региона:2"},
                "meta_params": {
                        "rfbn_id":{
                            "display_name": "Код региона",
                            "type": "string",
                            "length": 2,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                "name": "Участники ЕП, в разрезе регионов",
                "num_rep": "03",
                "proc": "rep_dia_cp_03",
                "data_approve": "12.09.2023",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по"},
                },
                {
                "name": "Списочная часть чистых ЕП-шников(СВ)",
                "num_rep": "04",
                "proc": "rep_dia_cp_04",
                "data_approve": "27.10.2023",
                "author": "Адильханова А.К.",
                "params": {"date_first": "С", "date_second": "по"},
                },
                {
                "name": "Списочная часть смешанных ЕП-шников(СВ)",
                "num_rep": "05",
                "proc": "rep_dia_cp_05",
                "data_approve": "31.10.2023",
                "author": "Адильханова А.К.",
                "params": {"date_first": "С", "date_second": "по"},
                }
            ]
        },
        {
            "grp_name": "Пл.Занятость", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.pz",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Сведения о численности участников и сумм их СО",
                    "num_rep": "01",
                    "proc": "rep_dia_pz_01",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                "name": "Участники ПЗ, в разрезе пола и возраста",
                "num_rep": "02",
                "proc": "rep_dia_pz_02",
                "data_approve": "26.11.2024",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по", "srfbn_id": "Код региона:2"},
                "meta_params": {
                        "rfbn_id":{
                            "display_name": "Код региона",
                            "type": "string",
                            "length": 2,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                }
                },
                {
                "name": "Участники ПЗ, в разрезе регионов",
                "num_rep": "03",
                "proc": "rep_dia_pz_03",
                "data_approve": "26.11.2024",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "C", "date_second": "по"},
                },
                {
                "name": "Списочная часть чистых ПЗ-шников(СВ)",
                "num_rep": "04",
                "proc": "rep_dia_pz_04",
                "data_approve": "26.11.2024",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "С", "date_second": "по"},
                },
                {
                "name": "Списочная часть смешанных ПЗ-шников(СВ)",
                "num_rep": "05",
                "proc": "rep_dia_pz_05",
                "data_approve": "26.11.2024",
                "author": "Гусейнов Ш.А.",
                "params": {"date_first": "С", "date_second": "по"},
                }
            ]
        },
        {
            "grp_name": "ЕСП", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.esp",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Списочная часть чистых ЕСП-шников",
                    "num_rep": "01",
                    "proc": "rep_dia_esp_01",
                    "data_approve": "25.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Списочная часть смешанных ЕСП-шников",
                    "num_rep": "02",
                    "proc": "rep_dia_esp_02",
                    "data_approve": "25.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Списочная часть смешанных ЕСП-шников(СВ)",
                    "num_rep": "03",
                    "proc": "rep_dia_esp_03_sv",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Списочная часть чистых ЕСП-шников(СВ)",
                    "num_rep": "04",
                    "proc": "rep_dia_esp_04_sv",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            ]
        },
        {
            "grp_name": "минСО", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.minCO",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Списочная часть по социальным отчислениям, меньшим установленного минимального уровня",
                    "num_rep": "01",
                    "proc": "rep_dia_co_01",
                    "data_approve": "14.07.2023",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Период:"}
                },
                {
                    "name": "Мониторинг поступления СО от плательщиков, с которыми проведена информационно-разъяснительная работ",
                    "num_rep": "02",
                    "proc": "rep_dia_co_02",
                    "data_approve": "10.04.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Любая дата:"}
                },
                {
                    "name": "Уплаченные СО в размере менее 1 МЗП за квартал. Для проведения информационно-разъяснительной работы",
                    "num_rep": "03",
                    "proc": "rep_dia_co_03",
                    "data_approve": "29.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Любой день квартала:"}
                },
                {
                    "name": "Списочная часть по социальным отчислениям, меньшим установленного минимального уровня (для ДГД)",
                    "num_rep": "04",
                    "proc": "rep_dia_co_01_dgd",
                    "data_approve": "20.02.2026",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Период:"}
                },
            ]
        },
        {
            "grp_name": "Консолидированные отчеты", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.consolidated",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Количество участников и суммы взносов по частоте участия за период",
                    "num_rep": "01",
                    "proc": "rep_dia_freq_so_01",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "СО по КНП, регионам, количеству участников и сумм (5СО)",
                    "num_rep": "02",
                    "proc": "rep_dia_5CO",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Выплаты по регионам и коду выплаты (7CP)",
                    "num_rep": "03",
                    "proc": "rep_dia_7CP",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Выплаты по регионам и коду выплаты (7CP-СВбр)",
                    "num_rep": "04",
                    "proc": "rep_dia_7CP_0704",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Выплаты по регионам и коду выплаты (7CP-СВбр-301)",
                    "num_rep": "05",
                    "proc": "rep_dia_7CP_07040301",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Выплаты по коду выплаты и регионам (6CB)",
                    "num_rep": "06",
                    "proc": "rep_dia_6CB",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Сведения о СВбр, назначенный размер которых составил 3 млн. тенге и более в разрезе регионов",
                    "num_rep": "07",
                    "proc": "rep_dia_3m",
                    "data_approve": "24.02.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Первый год:"},
                },
                {
                    "name": "Сведения о назначенных социальных выплатах, включенных (поставленных) на выплату (статус 20) ",
                    "num_rep": "08",
                    "proc": "rep_dia_20status",
                    "data_approve": "14.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                {
                    "name": "Динамика числености получателей и сумм СО",
                    "num_rep": "09",
                    "proc": "rep_dia_dynamic",
                    "data_approve": "22.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {
                        "date_first": {
                            "display_name": "За",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                    }
                },
            ]



        },
        {
            "grp_name": "Списки", 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.lists",
            "live_time": "0",
            "list": 
            [
                {
                    "name": "Список получателей со статусом '7' или '20'",
                    "num_rep": "01",
                    "proc": "rep_dia_list_01",
                    "data_approve": "14.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по", "rfpm_id": "Код выплаты"},
                    "meta_params": {
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "status":{
                            "display_name": "Статус",
                            "type": "enum",
                            "values": [7,20],
                            "required": True
                        }
                    }
                }   
            ]
        },
    ]
    ,
    "ДСР":
    [
        {
            "grp_name": "Выплаты",
            "live_time": "100",
            "module_dir": f"{REPORT_MODULE_PATH}.DSR",
            "list": [
                {
                    "name": "Контроль сроков по выплатам",
                    "num_rep": "01",
                    "proc": "dsr_01",
                    "data_approve": "11.10.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
            ]
        }
    ]
    ,
    "АКТУАРИИ":
    [
        {
            "grp_name": "Соц.Выплаты",
            "live_time": "0",
            "deps": ['02DARa',],
            "module_dir": f"{REPORT_MODULE_PATH}.AKTUAR",
            "list": [
                {
                    "name": "Загрузка AKTUAR_DEPENDANT",
                    "num_rep": "01",
                    "proc": "upload_aktuar_dependand",
                    "data_approve": "21.04.2025",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Месяц загрузки"},
                },
            ]
        }
    ]
    ,
    "ДМЭН":
    [
        {
            "grp_name": "Макеты",
            "live_time": "0",
            "module_dir": f"{REPORT_MODULE_PATH}.DMN",
            "list": [
                {
                "name": "Количество дел по дням и регионам без доработки",
                "num_rep": "01",
                "proc": "rep_dmn_01",
                "data_approve": "11.10.2023",
                "author": "Адильханова А.",
                "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                "name": "Количество дел по дням и регионам без доработки с ИИН-ами",
                "num_rep": "02",
                "proc": "rep_dmn_01_iin",
                "data_approve": "11.10.2023",
                "author": "Адильханова А.",
                "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                "name": "Количество дел по дням и регионам с доработкой",
                "num_rep": "03",
                "proc": "rep_dmn_02",
                "data_approve": "01.11.2023",
                "author": "Адильханова А.",
                "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                "name": "Количество дел по дням и регионам с доработкой с ИИН-ами",
                "num_rep": "04",
                "proc": "rep_dmn_02_iin",
                "data_approve": "01.11.2023",
                "author": "Адильханова А.",
                "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                    "name": "Количество дел по дням и регионам с доработкой 145",
                    "num_rep": "05",
                    "proc": "rep_dmen_145_with8",
                    "data_approve": "07.12.2023",
                    "author": "Адильханова А.",
                    "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                },
                {
                    "name": "Количество дел по дням и регионам с доработкой 145 ИИН-ы",
                    "num_rep": "06",
                    "proc": "rep_dmen_145_with8_iin",
                    "data_approve": "07.12.2023",
                    "author": "Адильханова А.",
                    "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                } 
                ,
                {
                "name": "Необратившиеся отказные",
                "num_rep": "07",
                "proc": "rep_dmn_12",
                "data_approve": "29.01.2024",
                "author": "Адильханова А.",
                "params": {"rfpm_id": "Код выплаты", "date_first": "С", "date_second": "по"},
                    "meta_params": {
                        "rfpm_id":{
                            "display_name": "Код выплаты",
                            "type": "string",
                            "length": 8,
                            "required": False
                        },
                        "date_first": {
                            "display_name": "C",
                            "type": "date",
                            "length": None,
                            "required": True
                        },
                        "date_second": {
                            "display_name": "по",
                            "type": "date",
                            "length": None,
                            "required": True
                        }
                    }
                }                
            ]
        }
    ]
    ,    
}