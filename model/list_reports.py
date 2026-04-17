from app_config import REPORT_MODULE_PATH

# live_time - время жизни отчета в часах, может указываться с 2 знаками после запятой
# в этом случае минимальное время жизни отчета составляет 36 секунд

DATE_FROM = {
    "display_name": "C",
    "type": "date",
    "length": None
}
DATE_TO = {
    "display_name": "по",
    "type": "date",
    "length": None
}


dict_reports = {
    "ДИА": 
    {
        "1501" : {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1501",
            "live_time": 0,
            "reports": 
            {
                "01": {
                    "name": "Количество иждивенцев и сумма 0701 за период",
                    "proc": "rep_0701_01",
                    "data_approve": "13.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Списочный состав иждивенцев",
                    "proc": "rep_0701_02",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "Списочный состав получателей 0701, с ребенком до 3 лет",
                    "proc": "rep_0701_03",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Списочный состав получателей 0701, с иждивенцем старше 18 лет",
                    "proc": "rep_0701_04",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05":{
                    "name": "Списки умерших кормильцев по действующим СВ",
                    "proc": "rep_0701_05",
                    "data_approve": "27.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "1502": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1502",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Получатели СВут 0702 за месяц",
                    "proc": "rep_0702_01",
                    "data_approve": "14.02.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "На"},
                },
                "02": {
                    "name": "Получатели СВут 0702 за период",
                    "proc": "rep_0702_02",
                    "data_approve": "21.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "Получатели СВут 0702 за период c 1 разделом",
                    "proc": "rep_0702_03",
                    "data_approve": "20.01.2026",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},

                    "meta_params": {
                       "date_first": DATE_FROM,
                       "date_second": DATE_TO
                    }
                }
            }
        },
        "1503": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1503",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "СО после окончания СВпр, в градации по месяцам после даты окончания выплаты",
                    "proc": "rep_0703_01",
                    "data_approve": "22.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "На"},
                },
                "02": {
                    "name": "Получатели СВпр, выплата которым назначена в тот же месяц, что и месяц окончания СВпр",
                    "proc": "rep_0703_02",
                    "data_approve": "23.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Выберите месяц: "},
                },
                "03": {
                    "name": "Получатели СВпр за период",
                    "proc": "rep_0703_03",
                    "data_approve": "22.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "1504": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1504",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Получатели СВбр и СВур, у которых между датами назначения есть СВпр",
                    "proc": "rep_0704_01",
                    "data_approve": "30.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Получатели СВбр",
                    "proc": "rep_0704_02",
                    "data_approve": "21.12.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "Получатели СВбр за период с СО между датой риска и датой окончания",
                    "proc": "rep_0704_03",
                    "data_approve": "18.10.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Получатели СВбр за период с количеством месяцев участия СО",
                    "proc": "rep_0704_04",
                    "data_approve": "28.09.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Получатели СВбр с назначенными выплатами более 3 млн.",
                    "proc": "rep_0704_05",
                    "data_approve": "24.04.2025",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Выберите начальную дату:"},
                },
                
            }
        },
        "1505": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1505",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Получатели СВур",
                    "proc": "rep_0705_01",
                    "data_approve": "30.06.2023",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
            }
        },
        "300": { 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.300",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Сведения о поступивших возвратах излишне зачисленных (выплаченных) сумм социальных выплат. Отчет 9V для Министерства",
                    "proc": "rep_dia_300_09",
                    "data_approve": "13.06.2023",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Список плательщиков, уплативших социальные отчисления за работников с численностью более 50 человек хотя бы 1 раз за предыдущие 6 месяцев",
                    "proc": "rep_dia_50",
                    "data_approve": "26.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "3000": { 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3000",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "СО по категориям МЗП и регионам (3029)",
                    "proc": "rep_dia_3029",
                    "data_approve": "14.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Стаж участия в СОСС (3023)",
                    "proc": "rep_dia_3023",
                    "data_approve": "12.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "СО по категориям МЗП и районам (3029-районы)",
                    "proc": "rep_dia_3029_1",
                    "data_approve": "14.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Возвраты социальных выплат по получателю",
                    "proc": "rep_dia_3030",
                    "data_approve": "15.04.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"iin": "C"},
                    "living_time": "at_once",
                    "meta_params": {
                        "iin":{
                            "display_name": "ИИН",
                            "type": "string",
                            "length": 12,
                            "required": True
                        },

                    }
                },
            }
        },

        "6020": { 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.6020",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Список лиц, которым назначена социальная выплата на случай потери кормильца",
                    "proc": "rep_dia_6021",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Список лиц, которым назначена социальная выплата на случай утраты трудоспособности",
                    "proc": "rep_dia_6022",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03":  {
                    "name": "Список лиц, которым назначена социальная выплата на случай потери работы",
                    "proc": "rep_dia_6023",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Список лиц, которым назначена социальная выплата на случай потери дохода в связи с беременностью и родами, усыновлением/удочерением ребенка",
                    "proc": "rep_dia_6024",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Список лиц, которым назначена социальная выплата 0704 и которые платили сами за себя",
                    "proc": "rep_dia_6024_1",
                    "data_approve": "14.09.2023",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "06": {
                    "name": "Список лиц, которым назначена социальная выплата на случай потери дохода в связи с уходом за ребенком по достижении им возраста 1 года",
                    "proc": "rep_dia_6025",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                }

            }
        },
        "ЕдПлатеж": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.cp",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Сведения о численности участников и сумм их СО",
                    "proc": "rep_dia_cp_01",
                    "data_approve": "12.07.2023",
                    "author": "Адильханова А.К.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Участники ЕП, в разрезе пола и возраста",
                    "proc": "rep_dia_cp_02",
                    "data_approve": "10.06.2023",
                    "author": "Адильханова А.К.",
                    "params": {"date_first": "С", "date_second": "по", "srfbn_id": "Код региона:2"},
                    "meta_params": 
                    {
                        "rfbn_id":{
                            "display_name": "Код региона",
                            "type": "string",
                            "length": 2,
                            "required": False
                        },
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Участники ЕП, в разрезе регионов",
                    "proc": "rep_dia_cp_03",
                    "data_approve": "12.09.2023",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Списочная часть чистых ЕП-шников(СВ)",
                    "proc": "rep_dia_cp_04",
                    "data_approve": "27.10.2023",
                    "author": "Адильханова А.К.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Списочная часть смешанных ЕП-шников(СВ)",
                    "proc": "rep_dia_cp_05",
                    "data_approve": "31.10.2023",
                    "author": "Адильханова А.К.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "Пл.Занятость": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.pz",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Сведения о численности участников и сумм их СО",
                    "proc": "rep_dia_pz_01",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Участники ПЗ, в разрезе пола и возраста",
                    "proc": "rep_dia_pz_02",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по", "srfbn_id": "Код региона:2"},
                    "meta_params": {
                        "rfbn_id":{
                            "display_name": "Код региона",
                            "type": "string",
                            "length": 2,
                            "required": False
                        },
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Участники ПЗ, в разрезе регионов",
                    "proc": "rep_dia_pz_03",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Списочная часть чистых ПЗ-шников(СВ)",
                    "proc": "rep_dia_pz_04",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Списочная часть смешанных ПЗ-шников(СВ)",
                    "proc": "rep_dia_pz_05",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "ЕСП": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.esp",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Списочная часть чистых ЕСП-шников",
                    "proc": "rep_dia_esp_01",
                    "data_approve": "25.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Списочная часть смешанных ЕСП-шников",
                    "proc": "rep_dia_esp_02",
                    "data_approve": "25.07.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "Списочная часть смешанных ЕСП-шников(СВ)",
                    "proc": "rep_dia_esp_03_sv",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Списочная часть чистых ЕСП-шников(СВ)",
                    "proc": "rep_dia_esp_04_sv",
                    "data_approve": "14.09.2023",
                    "author": "Алиманов Д.Д.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },
        "минСО": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.minCO",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Списочная часть по социальным отчислениям, меньшим установленного минимального уровня",
                    "proc": "rep_dia_co_01",
                    "data_approve": "14.07.2023",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Период:"}
                },
                "02": {
                    "name": "Мониторинг поступления СО от плательщиков, с которыми проведена информационно-разъяснительная работ",
                    "proc": "rep_dia_co_02",
                    "data_approve": "10.04.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Любая дата:"}
                },
                "03": {
                    "name": "Уплаченные СО в размере менее 1 МЗП за квартал. Для проведения информационно-разъяснительной работы",
                    "proc": "rep_dia_co_03",
                    "data_approve": "29.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Любой день квартала:"}
                },
                "04": {
                    "name": "Списочная часть по социальным отчислениям, меньшим установленного минимального уровня (для ДГД)",
                    "proc": "rep_dia_co_01_dgd",
                    "data_approve": "20.02.2026",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Период:"}
                },
            }
        },
        "Консолидированные отчеты": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.consolidated",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Количество участников и суммы взносов по частоте участия за период",
                    "proc": "rep_dia_freq_so_01",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "СО по КНП, регионам, количеству участников и сумм (5СО)",
                    "proc": "rep_dia_5CO",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "03": {
                    "name": "Выплаты по регионам и коду выплаты (7CP)",
                    "proc": "rep_dia_7CP",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Выплаты по регионам и коду выплаты (7CP-СВбр)",
                    "proc": "rep_dia_7CP_0704",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Выплаты по регионам и коду выплаты (7CP-СВбр-301)",
                    "proc": "rep_dia_7CP_07040301",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "06": {
                    "name": "Выплаты по коду выплаты и регионам (6CB)",
                    "proc": "rep_dia_6CB",
                    "data_approve": "28.01.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "07": {
                    "name": "Сведения о СВбр, назначенный размер которых составил 3 млн. тенге и более в разрезе регионов",
                    "proc": "rep_dia_3m",
                    "data_approve": "24.02.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "Первый год:"},
                },
                "08": {
                    "name": "Сведения о назначенных социальных выплатах, включенных (поставленных) на выплату (статус 20) ",
                    "proc": "rep_dia_20status",
                    "data_approve": "14.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "09": {
                    "name": "Динамика числености получателей и сумм СО",
                    "proc": "rep_dia_dynamic",
                    "data_approve": "22.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {
                        "date_first": DATE_FROM,
                    }
                },
            }

        },
        "Списки": {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.lists",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Список получателей со статусом '7' или '20'",
                    "proc": "rep_dia_list_01",
                    "data_approve": "14.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по", "rfpm_id": "Код выплаты"},
                    "meta_params": {
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO,
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
            }
        },
    }
    ,
    "ДСР":
    {
        "Выплаты": {
            "live_time": 100,
            "module_dir": f"{REPORT_MODULE_PATH}.DSR",
            "reports": 
            {
                "01": {
                    "name": "Контроль сроков по выплатам",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
            }
        }
    }
    ,
    "АКТУАРИИ":
    {
        "Соц.Выплаты": {
            "live_time":  0,
            "module_dir": f"{REPORT_MODULE_PATH}.AKTUAR",
            "reports": 
            {
                "03": {
                    "name": "Загрузка AKTUAR_DEPENDANT",
                    "proc": "upload_aktuar_dependand",
                    "data_approve": "21.04.2025",
                    "author": "Гусейнов Ш.",
                    "params": {"date_first": "Месяц загрузки"},
                },
            }
        }
    }
    ,
    "ДМЭН":
    {
        "Макеты": {
            "live_time":  0,
            "module_dir": f"{REPORT_MODULE_PATH}.DMN",
            "reports": 
            {
                "01": {
                    "name": "Количество дел по дням и регионам без доработки",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "02": {
                    "name": "Количество дел по дням и регионам без доработки с ИИН-ами",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Количество дел по дням и регионам с доработкой",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "04": {
                    "name": "Количество дел по дням и регионам с доработкой с ИИН-ами",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "05": {
                    "name": "Количество дел по дням и регионам с доработкой 145",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "06": {
                    "name": "Количество дел по дням и регионам с доработкой 145 ИИН-ы",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                } 
                ,
                "07": {
                    "name": "Необратившиеся отказные",
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
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                }                
            }
        }
    }
    ,    
}