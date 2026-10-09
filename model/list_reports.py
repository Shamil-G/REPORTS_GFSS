from app_config import REPORT_MODULE_PATH
from regions import regions
from util.period import period_choices
from datetime import date
import re

# live_time - время жизни отчета в часах, может указываться с 2 знаками после запятой
# в этом случае минимальное время жизни отчета составляет 36 секунд

# Шаг 1: Собираем только пары "код: имя" в чистый словарь
# Собираем чистый плоский словарь, который идеально переварит ваш HTML-шаблон
# 1. Сначала собираем чистый плоский словарь регионов
regions_values = {}
for code, data in regions.items():
    # «00 - ГФСС, Центр» в списке не показывается: вся республика - это пустое
    # значение области, а не код (см. отчёты с параметром rfbn_id).
    if code[:2] == '00':
        continue
    name = data.get('legacy_name', '')
    name = re.sub(r'^\s*\d{2}\s*-\s*', '', name).strip()
    regions_values[code[:2]] = f"{code[:2]} - {name}"

# 2. Описываем базовые метаданные регионов
# По умолчанию ставим required: False (или True, как вам удобнее)
LIST_REGION = {
    "display_name": "Выберите область",
    "type": "list",
    "length": 2,
    "required": False,          # По умолчанию необязательное
    "empty_label": "Вся республика",   # подпись пустого пункта: пусто - без фильтра по области
    "values": regions_values     # Наш плоский словарь уходит в ключ 'values'
}
  
DATE_FROM = {
    "display_name": "C",
    "type": "date",
    "required": True,
    "length": None
}
DATE_TO = {
    "display_name": "по",
    "type": "date",
    "required": True,
    "length": None
}

# Параметры отчётов, перенесённых из REP_STAT_EXTEND: вместо ~135 процедур-обёрток
# app_NN_1m / _2k / _3hy / _4_9m / _5y отчётный период стал обычным параметром.
#
# Год и период - выпадающие списки, а не поля ввода: руками в поле можно набрать
# что угодно, вплоть до букв.

# Значения, зависящие от текущей даты. Считаются не здесь, а при каждом показе
# формы (model/reports_info.py), иначе список годов застынет на дате импорта
# модуля и после Нового года в нём не будет текущего года.
DYNAMIC_VALUES = {
    "years": lambda: {str(y): str(y)
                      for y in range(date.today().year, 2004, -1)},
    "current_year": lambda: str(date.today().year),
    "current_month": lambda: f"1.{date.today().month}",
    "current_quarter": lambda: f"2.{(date.today().month - 1) // 3 + 1}",
    "current_ytd": lambda: f"7.{date.today().month}",
}

REP_YEAR = {
    "display_name": "Год",
    "type": "list",
    "required": True,
    "values": {},                  # заполняется из DYNAMIC_VALUES
    "dynamic": {"values": "years", "default": "current_year"},
}
# Одно поле вместо пары "тип периода" + "№ периода": значение "2.3" несёт и то,
# и другое (см. util/period.py). Номер периода сам по себе пользователю ничего
# не говорит, поэтому отдельным полем не показывается.
# По умолчанию текущий месяц: годовой отчёт снимается раз в год, месячный - всегда.
PERIOD = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices(),
    "dynamic": {"default": "current_month"},
}

# Расширенный список периодов для отчётов, у которых, помимо стандартных
# пяти типов, зарегистрирован ещё тип 6 (24 месяца) - например app_47,
# app_48 (см. migration-plan.md, "period_choices((1, 2, 3, 4, 5, 6))").
PERIOD_24M = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices((1, 2, 3, 4, 5, 6)),
    "dynamic": {"default": "current_month"},
}

# То же самое с типом 7 (произвольное число месяцев с начала года) вместо
# 6 - для app_49_1 (регистрация только месяц/7mn, но период_label
# поддерживает все стандартные типы + 7).
PERIOD_7 = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices((1, 2, 3, 4, 5, 7)),
    "dynamic": {"default": "current_month"},
}

# Только "с начала года по месяц" (тип 7) - для app_33: годовая таблица, которая
# снимается каждый месяц, каждый срез - отдельный файл.
PERIOD_YTD = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices((7,)),
    "dynamic": {"default": "current_ytd"},
}

# Только квартал - для app_54, чья структура (квартал / тот же квартал год
# назад / с начала года) осмысленна лишь для квартального периода.
PERIOD_QUARTER = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices((2,)),
    "dynamic": {"default": "current_quarter"},
}

# Только месяц - для формы 18 REP_MINTRUD (f11): Rep_11 читает лишь
# месячные данные, расчёт за другие периоды смысла не имеет.
PERIOD_MONTH = {
    "display_name": "Период",
    "type": "list",
    "required": True,
    "values": period_choices((1,)),
    "dynamic": {"default": "current_month"},
}

# Параметр отчётов app_38_v2/app_39_v2: учитывать ли при расчёте
# коэффициента замещения государственную базовую пенсию (ГСП). В PL/SQL это
# третий числовой параметр формы (Rep.ParAsNumb(3): 1 -> 'g', 2 -> 'n');
# здесь - обычный список с фиксированным значением по умолчанию "без учёта".
GSP = {
    "display_name": "Учёт ГСП",
    "type": "list",
    "required": True,
    "values": {
        "n": "без учета ГСП",
        "g": "с учетом ГСП",
    },
    "default": "n",
}

# Список кодов вывыплаты для выпадающего списка:
LIST_RFPM = {
            "display_name": "Выберите код выплаты",
            "type": "list",
            "length": 4,
                "values": {
              "0701": "0701 - Социальная выплата по потере кормильца",
              "0702": "0702 - Социальная выплата по утрате трудоспособности",
              "0703": "0703 - Социальная выплата по потере работы",
              "0704": "0704 - Социальная выплата по беременности и родам",
              "0705": "0705 - Социальная выплата по уходу за ребенком до года/до полутора лет",
            }
            }

dict_reports = {
    "ДИА": 
    {
        "100 - Отчеты по выплатам":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.100",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "1 - Анализ назначения социальных выплат с начала года",
                    "proc": "rep_dia_1",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "02": {
                    "name": "2 - Социальные выплаты из АО \"ГФСС\" через ГЦВП по РК",
                    "proc": "rep_dia_2",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "03": {
                    "name": "4 - Мониторинг движения макетов дел",
                    "proc": "rep_dia_4",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rfpm_kind": {"display_name": "Вид выплаты", "type": "list", "required": True, "values": {"1": "1 - по потере кормильца", "2": "2 - по утрате трудоспособности", "3": "3 - по потере работы", "4": "4 - по потере дохода в связи с беременностью и родами", "5": "5 - по потере дохода по уходу до 1 года", "6": "6 - по потере дохода в связи с усыновлением (удочерением) новорожденного"}}},
                },
                "04": {
                    "name": "5 - Анализ поступлений социальных отчислений и социальных выплат из Фонда",
                    "proc": "rep_dia_5",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR},
                },
                "05": {
                    "name": "8 - Сравнительный анализ получателей соц выплат и ГСП",
                    "proc": "rep_dia_8",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {},
                },
                "06": {
                    "name": "9 - Сведения о назначенных социальных выплатах из АО «ГФСС» по случаю потери работы",
                    "proc": "rep_dia_9",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "07": {
                    "name": "10 - «Еженедельные» оперативные сведения о назначенных социальных выплатах",
                    "proc": "rep_dia_10",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "08": {
                    "name": "11 - «Еженедельные» оперативные сведения об обратившихся за назначением социальных выплат",
                    "proc": "rep_dia_11",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "09": {
                    "name": "12 - Сведения об участниках системы социального страхования, обратившихся за социальной выплатой по случаю потери работы",
                    "proc": "rep_dia_12",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "10": {
                    "name": "13 - СВЕДЕНИЯ о назначенных социальных выплатах из АО «ГФСС» по случаю потери работы",
                    "proc": "rep_dia_13",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "11": {
                    "name": "17 - 100-9 По регионам",
                    "proc": "rep_dia_17",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
            }
        },
        "300": 
        { 
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
                },
                # ДУБЛИРУЕТСЯ по сообщению Заказчика (02.10.2026), форма REP_MINTRUD (Rep_Mintrud.pck, f3): AIS - группа «Отчёты в МинТруд» (300)
                # "03": {
                #     "name": "СО, пеня и число участников СОСС по региону "
                #             "(Форма 3)",
                #     "proc": "f3",
                #     "data_approve": "30.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_24M,
                #     }
                # },
                # ДУБЛИРУЕТСЯ по сообщению Заказчика (02.10.2026), форма REP_MINTRUD (Rep_Mintrud.pck, f4): AIS - группа «Отчёты в МинТруд» (300)
                # "04": {
                #     "name": "Получатели и суммы СВ по региону и виду "
                #             "выплаты (Форма 4)",
                #     "proc": "f4",
                #     "data_approve": "30.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # ДУБЛИРУЕТСЯ по сообщению Заказчика (02.10.2026), форма REP_MINTRUD (Rep_Mintrud.pck, f5): AIS - группа «Отчёты в МинТруд» (300)
                # "05": {
                #     "name": "Средний размер назначенных СВ по региону и "
                #             "виду выплаты (Форма 5)",
                #     "proc": "f5",
                #     "data_approve": "30.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # ДУБЛИРУЕТСЯ по сообщению Заказчика (02.10.2026), форма REP_MINTRUD (Rep_Mintrud.pck, f11): AIS - группа «Отчёты в МинТруд» (300)
                "06": {
                    "name": "Динамика численности получателей СВ за месяц "
                            "по виду выплаты (Приложение 18)",
                    "proc": "f11",
                    "data_approve": "01.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD_MONTH,
                    }
                },
            }
        },
        "500":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.500",
            "live_time": 0,
            "reports":
                {
                    "01": {
                        "name": "501 - Сведения о количестве участников СОСС",
                        "proc": "rep_dia_501",
                        "data_approve": "14.03.2025",
                        "author": "Туржанова Ж.Е.",
                        "meta_params":
                            {
                                "date_first": {
                                    "display_name": "C",
                                    "type": "date",
                                    "required": True
                                },
                                "rfbn_id": LIST_REGION
                            }
                    }
                }
        },
        "600 - Справки":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.600",
            "live_time": 0,
            "reports":
            {
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_601.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "01": {
                #     "name": "601 - Справка о произведенных выплатах",
                #     "proc": "rep_dia_601",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"iin": {"display_name": "ИИН получателя", "type": "string", "length": 12, "required": True}},
                # },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_602.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "02": {
                #     "name": "602 - Справка о доходах за год",
                #     "proc": "rep_dia_602",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"iin": {"display_name": "ИИН получателя", "type": "string", "length": 12, "required": True}, "date_first": DATE_FROM, "date_second": DATE_TO},
                # },
                "03": {
                    "name": "605 - Реестр беременных",
                    "proc": "rep_dia_605",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"iin": {"display_name": "ИИН получателя", "type": "string", "length": 12, "required": True}},
                },
            }
        },
        "1000 - Формы статотчётности в Мин. труд. 2014":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.1000",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "Оперативная отчетность по СВ из ГФСС (32 — Получатели и суммы СВ по видам риска)",
                    "proc": "app_32",
                    "data_approve": "28.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "02": {
                    "name": "Сведения о составе участников СОСС и суммах СО "
                            "(35 — в разрезе возраста и пола)",
                    "proc": "app_35",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "03": {
                    "name": "Число страховых случаев и суммы СВ по видам "
                            "(36 — в разрезе пола)",
                    "proc": "app_36",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "04": {
                    "name": "Число страховых случаев и суммы СВ по видам "
                            "(37 — в разрезе пола и возраста)",
                    "proc": "app_37",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "05": {
                    "name": "Коэффициент замещения дохода при утрате "
                            "трудоспособности (38)",
                    "proc": "app_38",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "06": {
                    "name": "Коэффициент замещения дохода при потере "
                            "кормильца (39)",
                    "proc": "app_39",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "07": {
                    "name": "Коэффициент замещения дохода по уходу за "
                            "ребёнком до года (41)",
                    "proc": "app_41",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "08": {
                    "name": "Получатели и суммы СВ по возрасту и стажу, "
                            "по виду выплаты (42-46)",
                    "proc": "app_42_46",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                        "rfpm_id": {**LIST_RFPM, "required": True},
                    }
                },
                "09": {
                    "name": "Количество назначенный СВ 0704.070403.0705 в разрезе стажа (52 — СВ по беременности и родам, усыновлению"
                            "и по уходу за ребёнком, по стажу в СОСС)",
                    "proc": "app_52",
                    "data_approve": "28.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "10": {
                    "name": "Количество плательщиков по БИН и ИИН в разрезе "
                            "регионов (53)",
                    "proc": "app_53",
                    "data_approve": "01.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "11": {
                    "name": "СВур, доведённые до ГСП, квартал к прошлому "
                            "году (54)",
                    "proc": "app_54",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD_QUARTER,
                    }
                },
                "12": {
                    "name": "Средний размер назначенных СВ по регионам и "
                            "видам риска (55)",
                    "proc": "app_55",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "13": {
                    "name": "Сведения по количеству получателей и суммам социальных выплат в разрезе регионов и стажа участия (1426)",
                    "proc": "rep_dia_1426",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO, "rfpm_id": {**LIST_RFPM, "required": True}},
                },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №02. REP_STAT_EXTEND.app_33_spool (+ Rep_app_33)
                # "14": {
                #     "name": "Динамика количества получателей социальных выплат "
                #             "из ГФСС по месяцам года (33)",
                #     "proc": "app_33",
                #     "data_approve": "01.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_YTD,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №03. REP_STAT_EXTEND.app_34_35_spool / Rep_app_34_35, ветка iRepNum='sex' (общая процедура с app_35 - он остаётся: ДИА / группа 1000, ключ 02); обёртки app_34_35_1m..7mn
                # "15": {
                #     "name": "Сведения о половозрастном составе участников СОСС и суммах СО "
                #             "(34 — в разрезе пола)",
                #     "proc": "app_34",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №11. REP_STAT_EXTEND.app_40_41_spool / Rep_app_40_41, iTypePay='0703' (общая процедура с app_41 - он остаётся: ДИА / группа 1000, ключ 07); обёртки app_40_41_1m..5y
                # "16": {
                #     "name": "Коэффициент замещения дохода при потере "
                #             "работы, по стажу в СОСС (40)",
                #     "proc": "app_40",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №14. REP_STAT_EXTEND.app_47_spool (+ Rep_app_47); обёртки app_47_1m..24m
                # "17": {
                #     "name": "Участники СОСС по уровню дохода, в разрезе "
                #             "пола (47)",
                #     "proc": "app_47",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_24M,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №15. REP_STAT_EXTEND.app_48_spool (+ Rep_app_48_24m); обёртка app_48_24m
                # "18": {
                #     "name": "Участники СОСС по стажу участия за 24 месяца, "
                #             "в разрезе пола (48)",
                #     "proc": "app_48",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_24M,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №16. REP_STAT_EXTEND.app_49_spool (+ Rep_app_49); обёртки app_49_2k/3hy/4_9m/5y
                # "19": {
                #     "name": "Обращения и назначения СВ по срокам "
                #             "рассмотрения (49)",
                #     "proc": "app_49",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №17. REP_STAT_EXTEND.app_49_1_spool (+ Rep_app_49_1); обёртки app_49_1_1m..7mn
                # "20": {
                #     "name": "Обращения и назначения СВ, метрика \"4 "
                #             "рабочих дня\", по региону и виду риска (49.1)",
                #     "proc": "app_49_1",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_7,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №18. REP_STAT_EXTEND.app_50_spool (+ Rep_app_50; app_50_spool_old - старая версия); обёртки app_50_1m..5y
                # "21": {
                #     "name": "Назначенные СВ в зависимости от дохода, по "
                #             "виду выплаты (50)",
                #     "proc": "app_50",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #         "rfpm_id": {**LIST_RFPM, "required": True},
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №19. REP_STAT_EXTEND.app_51_spool (+ Rep_app_51); обёртки app_51_1m..5y
                # "22": {
                #     "name": "СВ по беременности и родам, по стажу и "
                #             "интервалу суммы выплаты (51)",
                #     "proc": "app_51",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №24. REP_STAT_EXTEND.app_56_spool (+ Rep_app_56); обёртка app_56_1m
                # "23": {
                #     "name": "Динамика перехода степеней утраты "
                #             "трудоспособности получателей СВ 0702 (56)",
                #     "proc": "app_56",
                #     "data_approve": "01.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_MONTH,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №25. REP_STAT_EXTEND.app_57_spool (+ Rep_app_57); обёртка app_57_1m
                # "24": {
                #     "name": "Динамика изменения количества иждивенцев "
                #             "получателей СВ 0701 (57)",
                #     "proc": "app_57",
                #     "data_approve": "01.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD_MONTH,
                #     }
                # },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №26. REP_STAT_EXTEND.app_58_spool (+ Rep_app_58); обёртки app_58_1m..5y
                # "25": {
                #     "name": "Информация по оказанию услуг: назначения и "
                #             "отказы по каналам обращения (58)",
                #     "proc": "app_58",
                #     "data_approve": "01.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #     }
                # },
            }
        },
        "1501" : 
        {
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
        "1502": 
        {
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
                    "meta_params": {
                       "date_first": DATE_FROM,
                       "date_second": DATE_TO,
                    }
                }
            }
        },
        "1503": 
        {
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
        "1504": 
        {
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
        "1505": 
        {
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
        "2000 - Отчеты ГФСС 2014":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.2000",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "Коэффициент замещения дохода при утрате "
                            "трудоспособности, с выбором учёта ГСП (38, v2)",
                    "proc": "app_38_v2",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                        "gsp": GSP,
                    }
                },
                "02": {
                    "name": "Коэффициент замещения дохода при потере "
                            "кормильца, с выбором учёта ГСП (39, v2)",
                    "proc": "app_39_v2",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                        "gsp": GSP,
                    }
                },
                "03": {
                    "name": "Получатели и суммы СВур по очерёдности детей "
                            "(Форма 3)",
                    "proc": "app_f3",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                    }
                },
                "04": {
                    "name": "СВБР: получатели по доле МЗП, по виду "
                            "выплаты (табл. 2)",
                    "proc": "svbr_tab2",
                    "data_approve": "29.09.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rep_year": REP_YEAR,
                        "period": PERIOD,
                        "rfpm_id": {**LIST_RFPM, "required": True},
                    }
                },
                # УСТАРЕЛ по сообщению Заказчика (02.10.2026), №28. REP_STAT_EXTEND.svbr_tab1_2_spool / svbr_tab1_2, таблица 1 (общая процедура с таблицей 2 - он остаётся: ДИА / группа 2000, ключ 04); обёртки svbr_tab1_2_1m..5y
                # "05": {
                #     "name": "СВБР: получатели по стажу участия, по виду "
                #             "выплаты (табл. 1)",
                #     "proc": "svbr_tab1",
                #     "data_approve": "29.09.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {
                #         "rep_year": REP_YEAR,
                #         "period": PERIOD,
                #         "rfpm_id": {**LIST_RFPM, "required": True},
                #     }
                # },
            }
        },
        "3000": 
        { 
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3000",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "3001 - Ведомость возвращенных излишне уплаченных СО",
                    "proc": "rep_dia_3001",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "02": {
                    "name": "3005 - Сведения о градации вновь назначенных получателей социальных выплат",
                    "proc": "rep_dia_3005",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "03": {
                    "name": "3007 - Сведения о градации по годам назначения",
                    "proc": "rep_dia_3007",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH, "rfpm_id": {**LIST_RFPM, "required": True}},
                },
                "04": {
                    "name": "3009 - Сведения о численности получателей, за которых производятся ОПВ",
                    "proc": "rep_dia_3009",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "05": {
                    "name": "3011 - Сведения по первому разделу",
                    "proc": "rep_dia_3011",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "06": {
                    "name": "3016 - Реестр сумм возвратов социальных выплат(3107)",
                    "proc": "rep_dia_3016",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3019 - статус 103 (3103)",
                    "proc": "rep_dia_3019",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3020.КНП - Список возвратов СВ перечисленных в ГФСС",
                    "proc": "rep_dia_3020",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            },
                            "knp": {
                                "display_name": "КНП (через запятую)",
                                "type": "string",
                                "length": 40,
                                "width": 17,
                                "required": True
                            }
                        }
                },
                "09": {
                    "name": "3020.ИИН - Список возвратов СВ перечисленных в ГФСС (по ИИН)",
                    "proc": "rep_dia_3020_iin",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            },
                            "iin": {
                                "display_name": "ИИН",
                                "type": "string",
                                "length": 12,
                                "width": 17,
                                "required": True
                            }
                        }
                },
                "10": {
                    "name": "3022 - Аналитический отчет стаж участия в СОСС в разрезе возраста",
                    "proc": "rep_dia_3022",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "11": {
                    "name": "Стаж участия в СОСС (3023)",
                    "proc": "rep_dia_3023",
                    "data_approve": "12.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "12": {
                    "name": "3027 - Список лиц, являющихся плательщиками ЕСП, которым назначена социальная выплата",
                    "proc": "rep_dia_3027",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "13": {
                    "name": "СО по категориям МЗП и регионам (3029)",
                    "proc": "rep_dia_3029",
                    "data_approve": "14.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "14": {
                    "name": "СО по категориям МЗП и районам (3029-районы)",
                    "proc": "rep_dia_3029_1",
                    "data_approve": "14.03.2025",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "15": {
                    "name": "3030 - Отчет 9V (для Министерства)",
                    "proc": "rep_dia_3030",
                    "data_approve": "15.04.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "16": {
                    "name": "3100 - Ведомость перечисленных социальных выплат в разрезе БВУ",
                    "proc": "rep_dia_3100",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "17": {
                    "name": "3101 - Ведомость перечисленных ОПВ",
                    "proc": "rep_dia_3101",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "18": {
                    "name": "3102 - Ведомость перечисленных социальных выплат в разрезе областей",
                    "proc": "rep_dia_3102",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "19": {
                    "name": "3103 - Отчет о поступивших социальных отчислениях",
                    "proc": "rep_dia_3103",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "20": {
                    "name": "3104 - Список, возвратов ОПВ",
                    "proc": "rep_dia_3104",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            },
                            "knp": {
                                "display_name": "КНП",
                                "type": "string",
                                "length": 3,
                                "required": True
                            }
                        }
                },
                "21": {
                    "name": "3105 - Ведомость возвращенных излишне уплаченных СО",
                    "proc": "rep_dia_3105",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "22": {
                    "name": "3106 - Отчет о возвратах СО в разрезе видов ошибок",
                    "proc": "rep_dia_3106",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "23": {
                    "name": "3107 - Реестр сумм возвратов социальных выплат",
                    "proc": "rep_dia_3107",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "24": {
                    "name": "3108 - Отчет по платежам в разрезе КНП",
                    "proc": "rep_dia_3108",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "25": {
                    "name": "3109 - Количество взносов участников СОСС",
                    "proc": "rep_dia_3109",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "26": {
                    "name": "3110 - Численность участников СОСС, в разрезе пола и возраста",
                    "proc": "rep_dia_3110",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "27": {
                    "name": "3111 - Женщины-участники СОСС 50+, СО по БИН и ИИН",
                    "proc": "rep_dia_3111",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "28": {
                    "name": "3112 - Женщины-участники СОСС 50+, СО от нескольких работодателей",
                    "proc": "rep_dia_3112",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "29": {
                    "name": "3113 - Перевод денежных средств в АО 'ГФСС'",
                    "proc": "rep_dia_3113",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "30": {
                    "name": "3114 - Потребность",
                    "proc": "rep_dia_3114",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "31": {
                    "name": "3115 - График выплаты социальных выплат",
                    "proc": "rep_dia_3115",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"pay_day": {"display_name": "День выплаты", "type": "date", "required": True}, "pay_type": {"display_name": "Тип графика", "type": "list", "required": True, "default": "1", "values": {"1": "1 - выплаты, удержания и недополученное", "2": "2 - перечисления в НПФ (10%)"}}, "rfbn_id": LIST_REGION},
                },
                "32": {
                    "name": "3118 - График выплат",
                    "proc": "rep_dia_3118",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "33": {
                    "name": "3119 - Иностранные граждане (Участники СОСС)",
                    "proc": "rep_dia_3119",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "34": {
                    "name": "3120 - Иностранные граждане-получатели, в разрезе стран",
                    "proc": "rep_dia_3120",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "35": {
                    "name": "3121 - Иностранные граждане-получатели, в разрезе документов",
                    "proc": "rep_dia_3121",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "36": {
                    "name": "3122 - Сведения о числе получателей, количестве и суммах выплат",
                    "proc": "rep_dia_3122",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "37": {
                    "name": "3123 - Сведения о числе получателей по области",
                    "proc": "rep_dia_3123",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": DATE_FROM,
                            "date_second": DATE_TO,
                            "rfbn_id": LIST_REGION
                        }
                },
                "38": {
                    "name": "3124 - Сведения о размерах выплат по районам",
                    "proc": "rep_dia_3124",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                    {
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO,
                        "rfbn_id": LIST_REGION
                    }
                },
                "39":
                {
                    "name": "3125 - Сведения о числе получателей по полу по районам",
                    "proc": "rep_dia_3125",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                    {
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO,
                        "rfbn_id": LIST_REGION
                    }
                },
                # Дубль 3030 (та же процедура и те же параметры, что выше) - закомментирован 06.10.2026
                # "17": {
                #     "name": "3030 - Отчет 9V (для Министерства)",
                #     "proc": "rep_dia_3030",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # --- закомментированные отчёты (прежние ключи 05-12) ---
                # "05": {
                #     "name": "3003 - Оперативные сведения по социальным выплатам",
                #     "proc": "rep_dia_3003",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "06": {
                #     "name": "3004 - Сведения о градации состоявшихся получателей социальных выплат",
                #     "proc": "rep_dia_3004",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "07": {
                #     "name": "3005 - Сведения о градации вновь назначенных получателей социальных выплат",
                #     "proc": "rep_dia_3105",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "08": {
                #     "name": "3007 - Сведения о градации по годам назначения",
                #     "proc": "rep_dia_3007",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "09": {
                #     "name": "3008 - Сведения о половозрастной структуре получателей",
                #     "proc": "rep_dia_3108",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "10": {
                #     "name": "3009 - Сведения о численности получателей, за которых производятся ОПВ",
                #     "proc": "rep_dia_3109",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "11": {
                #     "name": "3011 - Сведения по первому разделу",
                #     "proc": "rep_dia_3011",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
                # "12": {
                #     "name": "3012 - Сведения по первому разделу в разрезе областей",
                #     "proc": "rep_dia_3012",
                #     "data_approve": "14.03.2025",
                #     "author": "Туржанова Ж.Е.",
                #     "meta_params":
                #         {
                #             "date_first": {
                #                 "display_name": "C",
                #                 "type": "date",
                #                 "required": True
                #             },
                #             "date_second": {
                #                 "display_name": "по",
                #                 "type": "date",
                #                 "required": True
                #             }
                #         }
                # },
            },
        },
        "3127 - Утрата трудоспособности": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3127",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3128 - Количество получателей и сумма в разрезе степени",
                    "proc": "rep_dia_3128",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3129 - Количество и средний размер в разрезе стажа участия",
                    "proc": "rep_dia_3129",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3130 - Градация СМД принятого для исчисления выплаты",
                    "proc": "rep_dia_3130",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3131 - Градация размеров получателей",
                    "proc": "rep_dia_3131",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3132 - Градация назначенных размеров",
                    "proc": "rep_dia_3132",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3133 - Количество месяцев принятых в расчет при назначении",
                    "proc": "rep_dia_3133",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3134 - Количество лет, на которые назначена выплата",
                    "proc": "rep_dia_3134",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3135 - Сведения о назначенных средних размерах по областям",
                    "proc": "rep_dia_3135",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "09": {
                    "name": "3136 - Половозрастная структура получателей",
                    "proc": "rep_dia_3136",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "10": {
                    "name": "3137 - Количество получателей и сумма выплаты по регионам",
                    "proc": "rep_dia_3137",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "11": {
                    "name": "3138 - Получатели, у которых удержаны ОПВ",
                    "proc": "rep_dia_3138",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "12": {
                    "name": "3139 - Структура получателей в разрезе пола",
                    "proc": "rep_dia_3139",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "13": {
                    "name": "3140 - Количество получателей по году назначения",
                    "proc": "rep_dia_3140",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3141 - Потеря кормильца": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3141",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3142 - Количество получателей и сумма в разрезе количества иждивенцев",
                    "proc": "rep_dia_3142",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3143 - Количество и средний размер в разрезе стажа участия",
                    "proc": "rep_dia_3143",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3144 - Градация СМД принятого для исчисления выплаты",
                    "proc": "rep_dia_3144",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3145 - Градация размеров получателей",
                    "proc": "rep_dia_3145",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3146 - Градация назначенных размеров",
                    "proc": "rep_dia_3146",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3147 - Количество месяцев принятых в расчет при назначении",
                    "proc": "rep_dia_3147",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3148 - Количество лет, на которые назначена выплата",
                    "proc": "rep_dia_3148",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3149 - Сведения о назначенных средних размерах по областям",
                    "proc": "rep_dia_3149",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "09": {
                    "name": "3150 - Половозрастная структура получателей",
                    "proc": "rep_dia_3150",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "10": {
                    "name": "3151 - Количество получателей и сумма выплаты по регионам",
                    "proc": "rep_dia_3151",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "11": {
                    "name": "3152 - Структура получателей в разрезе пола",
                    "proc": "rep_dia_3152",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "12": {
                    "name": "3153 - Количество получателей по году назначения",
                    "proc": "rep_dia_3153",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3154 - Потеря работы": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3154",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3155 - Количество получателей и сумма в разрезе количества месяцев",
                    "proc": "rep_dia_3155",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3156 - Количество и средний размер в разрезе стажа участия",
                    "proc": "rep_dia_3156",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3157 - Градация СМД принятого для исчисления выплаты",
                    "proc": "rep_dia_3157",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3158 - Градация размеров получателей",
                    "proc": "rep_dia_3158",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3159 - Градация назначенных размеров",
                    "proc": "rep_dia_3159",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3160 - Количество месяцев принятых в расчет при назначении",
                    "proc": "rep_dia_3160",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3161 - Сведения о назначенных средних размерах по областям",
                    "proc": "rep_dia_3161",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3162 - Половозрастная структура получателей",
                    "proc": "rep_dia_3162",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "09": {
                    "name": "3163 - Количество получателей и сумма выплаты по регионам",
                    "proc": "rep_dia_3163",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "10": {
                    "name": "3164 - Структура получателей в разрезе пола",
                    "proc": "rep_dia_3164",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3165 - По беременности и родам": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3165",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3166 - Количество получателей и сумма в разрезе видов",
                    "proc": "rep_dia_3166",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3167 - Градация СМД принятого для исчисления выплаты",
                    "proc": "rep_dia_3167",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3168 - Градация размеров получателей",
                    "proc": "rep_dia_3168",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3169 - Градация назначенных размеров",
                    "proc": "rep_dia_3169",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3170 - Количество месяцев принятых в расчет при назначении",
                    "proc": "rep_dia_3170",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3171 - Сведения о назначенных средних размерах по областям",
                    "proc": "rep_dia_3171",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3172 - Возрастная структура получателей",
                    "proc": "rep_dia_3172",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3173 - Количество получателей и сумма выплаты по регионам",
                    "proc": "rep_dia_3173",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3174 - По уходу за ребенком": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3174",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3175 - Количество получателей и сумма в разрезе количества детей",
                    "proc": "rep_dia_3175",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3176 - Градация СМД принятого для исчисления выплаты",
                    "proc": "rep_dia_3176",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3177 - Градация размеров получателей",
                    "proc": "rep_dia_3177",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3178 - Градация назначенных размеров",
                    "proc": "rep_dia_3178",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3179 - Количество месяцев принятых в расчет при назначении",
                    "proc": "rep_dia_3179",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3180 - Сведения о назначенных средних размерах по областям",
                    "proc": "rep_dia_3180",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "07": {
                    "name": "3181 - Половозрастная структура получателей",
                    "proc": "rep_dia_3181",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "08": {
                    "name": "3182 - Количество получателей и сумма выплаты по регионам",
                    "proc": "rep_dia_3182",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "09": {
                    "name": "3183 - Получатели, у которых удержаны ОПВ",
                    "proc": "rep_dia_3183",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "10": {
                    "name": "3184 - Структура получателей в разрезе пола",
                    "proc": "rep_dia_3184",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "11": {
                    "name": "3185 - Сведения по доплате",
                    "proc": "rep_dia_3185",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "12": {
                    "name": "3186 - Количество работодателей",
                    "proc": "rep_dia_3186",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3190 - Получатели СВ": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3190",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3191 - Утрата трудоспособности",
                    "proc": "rep_dia_3191",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "02": {
                    "name": "3192 - Потеря кормильца",
                    "proc": "rep_dia_3192",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "03": {
                    "name": "3193 - Потеря работы",
                    "proc": "rep_dia_3193",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "04": {
                    "name": "3194 - По беременности и родам",
                    "proc": "rep_dia_3194",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "05": {
                    "name": "3195 - По уходу за ребенком",
                    "proc": "rep_dia_3195",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
                "06": {
                    "name": "3196 - Назначение по всем видам выплаты",
                    "proc": "rep_dia_3196",
                    "data_approve": "14.03.2025",
                    "author": "Туржанова Ж.Е.",
                    "meta_params":
                        {
                            "date_first": {
                                "display_name": "C",
                                "type": "date",
                                "required": True
                            },
                            "date_second": {
                                "display_name": "по",
                                "type": "date",
                                "required": True
                            }
                        }
                },
            }
        },
        "3500 - Отчеты ЕСП":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.3500",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3502 - Отчет о поступивших СО от плательщиков ЕСП",
                    "proc": "rep_dia_3502",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rfbn_id": LIST_REGION, "date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "02": {
                    "name": "3503 - Отчет о сторнированных суммах единого совокупного платежа в разрезе видов ошибок",
                    "proc": "rep_dia_3503",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "03": {
                    "name": "3504 - Сведения о частоте уплаты ЕСП",
                    "proc": "rep_dia_3504",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_3505.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "04": {
                #     "name": "3505 - Участники системы социального страхования и одновременно уплачивающие ЕСП",
                #     "proc": "rep_dia_3505",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                # },
                "05": {
                    "name": "3506 - Отчет о поступивших СО от плательщиков ЕСП по периоду",
                    "proc": "rep_dia_3506",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rfbn_id": LIST_REGION, "date_first": DATE_FROM, "date_second": DATE_TO},
                },
            }
        },
        "6000 - Квартальные отчеты":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.6000",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "6001 - Кол-во работодателей для лиц с СВбр",
                    "proc": "rep_dia_6001",
                    "data_approve": "07.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_QUARTER},
                },
                "02": {
                    "name": "6002 - 1 МЗП квартальный",
                    "proc": "rep_dia_6002",
                    "data_approve": "07.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_QUARTER},
                },
            }
        },
        "6020": 
        { 
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
        "ЕдПлатеж": 
        {
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
                    "meta_params": 
                    {
                        "rfbn_id":{ **LIST_REGION, "required": False },
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
        "ЕСП": 
        {
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
        "Консолидированные отчеты": 
        {
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
                "10": {
                    "name": "Средние с начала года и за месяц",
                    "proc": "rep_dia_avg_so",
                    "data_approve": "07.10.2026",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
            }
        },
        "минСО": 
        {
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
        "Пл.Занятость": 
        {
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
                    "meta_params": {
                        "rfbn_id":{ **LIST_REGION, "required": False },
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
        "Самозанятые": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.sz",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Сведения о численности Самозанятых участников и сумм их СО",
                    "proc": "rep_dia_sz_01",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "02": {
                    "name": "Самозанятые участники, в разрезе пола и возраста",
                    "proc": "rep_dia_sz_02",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {
                        "rfbn_id":{ **LIST_REGION, "required": False },
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Самозанятые участники, в разрезе регионов",
                    "proc": "rep_dia_sz_03",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "04": {
                    "name": "Списочная часть чистых Самозаняты участников (СЗ)",
                    "proc": "rep_dia_sz_04",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                },
                "05": {
                    "name": "Списочная часть смешанных Самозанятых участников (СЗ)",
                    "proc": "rep_dia_sz_05",
                    "data_approve": "26.11.2024",
                    "author": "Гусейнов Ш.А.",
                    "params": {"date_first": "С", "date_second": "по"},
                }
            }
        },        
        "Списки": 
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DIA.lists",
            "live_time":  0,
            "reports": 
            {
                "01": {
                    "name": "Список получателей со статусом '7' или '20'",
                    "proc": "rep_dia_list_01",
                    "data_approve": "14.10.2025",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO,
                        "rfpm_id": LIST_RFPM,
                        "status":{
                            "display_name": "Статус",
                            "type": "enum",
                            "values": [7,20],
                            "required": True
                        }
                    }
                },  
                "02": {
                    "name": "Списки получателей выплат по регионам и кодам выплат",
                    "proc": "rep_dia_list_02",
                    "data_approve": "26.08.2026",
                    "author": "Гусейнов Ш.А.",
                    "meta_params": {
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO,
                        "rfbn_id": LIST_REGION,
                        "rfpm_id": {**LIST_RFPM, "required": False},
                    }
                },                  
            },
            

        },
      
    }
    ,
    "ДСР":
    {
        "Выплаты": 
        {
            "live_time": 100,
            "module_dir": f"{REPORT_MODULE_PATH}.DSR",
            "reports": 
            {
                "01": {
                    "name": "Контроль сроков по выплатам",
                    "proc": "dsr_01",
                    "data_approve": "11.10.2023",
                    "author": "Гусейнов Ш.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
            }
        },
        "3400":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DSR.3400",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3401 - Сведения о составе участников СОСС в разрезе количества работодателей",
                    "proc": "rep_dia_3401",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
            }
        },
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
        },
        "700":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.AKTUAR.700",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "708 - Средний возраст получателей по утрате трудоспособности",
                    "proc": "rep_dia_708",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "02": {
                    "name": "709 - Средний возраст иждивенцев",
                    "proc": "rep_dia_709",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rep_year": REP_YEAR, "period": PERIOD_MONTH},
                },
                "03": {
                    "name": "710 - Средневзвешенные КСУ",
                    "proc": "rep_dia_710",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "04": {
                    "name": "711 - Средние размеры по утрате трудоспособности",
                    "proc": "rep_dia_711",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "05": {
                    "name": "712 - Средние размеры по потере кормильца",
                    "proc": "rep_dia_712",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "06": {
                    "name": "713 - Средние размеры по потере работы",
                    "proc": "rep_dia_713",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "07": {
                    "name": "714 - Средняя продолжительность выплат по утрате трудоспособности (факт)",
                    "proc": "rep_dia_714",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "08": {
                    "name": "715 - Средняя продолжительность выплат по утрате трудоспособности (прогноз)",
                    "proc": "rep_dia_715",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "09": {
                    "name": "716 - Средняя продолжительность выплат по потере кормильца (факт)",
                    "proc": "rep_dia_716",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
            }
        },
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
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "02": {
                    "name": "Количество дел по дням и регионам без доработки с ИИН-ами",
                    "proc": "rep_dmn_01_iin",
                    "data_approve": "11.10.2023",
                    "author": "Адильханова А.",
                    "meta_params": {                    
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "02": {
                    "name": "Количество дел по дням и регионам без доработки с ИИН-ами",
                    "proc": "rep_dmn_01_iin",
                    "data_approve": "11.10.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Количество дел по дням и регионам с доработкой",
                    "proc": "rep_dmn_02",
                    "data_approve": "01.11.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "03": {
                    "name": "Количество дел по дням и регионам с доработкой",
                    "proc": "rep_dmn_02",
                    "data_approve": "01.11.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "04": {
                    "name": "Количество дел по дням и регионам с доработкой с ИИН-ами",
                    "proc": "rep_dmn_02_iin",
                    "data_approve": "01.11.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "05": {
                    "name": "Количество дел по дням и регионам с доработкой 145",
                    "proc": "rep_dmen_145_with8",
                    "data_approve": "07.12.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                },
                "06": {
                    "name": "Количество дел по дням и регионам с доработкой 145 ИИН-ы",
                    "proc": "rep_dmen_145_with8_iin",
                    "data_approve": "07.12.2023",
                    "author": "Адильханова А.",
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
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
                    "meta_params": {
                        "rfpm_id": LIST_RFPM,
                        "date_first": DATE_FROM,
                        "date_second": DATE_TO
                    }
                }
            }
        },
        "3300":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DMN.3300",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3316 - Назначение СВпр",
                    "proc": "rep_dia_3316",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "02": {
                    "name": "3320 - Список безработных",
                    "proc": "rep_dia_3320",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "03": {
                    "name": "3321 - Сведения по безработным",
                    "proc": "rep_dia_3321",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "04": {
                    "name": "3324 - Список получателей выплат на период ЧП и на период карантина(по БИН)",
                    "proc": "rep_dia_3324",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"bin": {"display_name": "БИН", "type": "string", "length": 12, "required": True}},
                },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_3325.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "05": {
                #     "name": "3325 - Макет по СВчп (по БИН)",
                #     "proc": "rep_dia_3325",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"bin": {"display_name": "БИН", "type": "string", "length": 12, "required": True}},
                # },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_3326.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "06": {
                #     "name": "3326 - Сведения по отказным выплатам 42500 в разрезе причин",
                #     "proc": "rep_dia_3326",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"rfbn_id": {**LIST_REGION, "required": True}, "date_first": DATE_FROM, "date_second": DATE_TO},
                # },
                "07": {
                    "name": "3327 - Количество отказанных дел по причинам, в разрезе областей",
                    "proc": "rep_dia_3327",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_3328.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "08": {
                #     "name": "3328 - Сведения по выплатам 42500 в разрезе причин",
                #     "proc": "rep_dia_3328",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"rfbn_id": {**LIST_REGION, "required": True}, "date_first": DATE_FROM, "date_second": DATE_TO},
                # },
                # НЕ ИСПОЛЬЗУЕТСЯ (02.10.2026): оригинал читает person.rn - колонки нет, значит отчёт не работает давно; модуль rep_dia_3329.py оставлен на случай, если отчёт понадобится (ИИН в нём - person.iin)
                # "09": {
                #     "name": "3329 - Получатель выплаты 42500 тенге (по ИИН)",
                #     "proc": "rep_dia_3329",
                #     "data_approve": "02.10.2026",
                #     "author": "Гусейнов Ш.",
                #     "meta_params": {"iin": {"display_name": "ИИН", "type": "string", "length": 12, "required": True}},
                # },
            }
        },
        "7000":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.DMN.7000",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "7001 - Сведения об оказанных услугах по отделениям",
                    "proc": "rep_dia_7001",
                    "data_approve": "07.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rfbn_id": LIST_REGION, "date_first": DATE_FROM, "date_second": DATE_TO},
                },
            }
        },
    }
    ,
    "ВОЗВРАТЫ":
    {
        "400":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.VOZVRATY.400",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "408 - Отчёт по возвращённым суммам",
                    "proc": "rep_dia_408",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "02": {
                    "name": "409 - Отчет по аннулированным",
                    "proc": "rep_dia_409",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
                "03": {
                    "name": "412 - Отчёт по возвращённым суммам (Для реестра)",
                    "proc": "rep_dia_412",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"date_first": DATE_FROM, "date_second": DATE_TO},
                },
            }
        },
        "3200":
        {
            "module_dir": f"{REPORT_MODULE_PATH}.VOZVRATY.3200",
            "live_time": 0,
            "reports":
            {
                "01": {
                    "name": "3201 - Справка о последней дате уплаты СО",
                    "proc": "rep_dia_3201",
                    "data_approve": "02.10.2026",
                    "author": "Гусейнов Ш.",
                    "meta_params": {"rnn": {"display_name": "РНН", "type": "string", "length": 12, "required": False}, "bin_iin": {"display_name": "БИН/ИИН", "type": "string", "length": 12, "required": False}},
                },
            }
        },
    }
    ,
}
