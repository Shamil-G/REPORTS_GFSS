# Система Отчетнотности на Python

## Система отчетности Фонда Python

$ git config --global user.name "Shamil-G"
$ git config --global user.email <s.gusseynov@gmail.com>

git remote add origin <https://github.com/Shamil-G/REPORTS_GFSS.git>
git branch -M main
git push -u origin main

## GFSSRegistry

Registry some users's action

git config --global user.name "Shamil-G"
git config --global user.email <s.gusseynov@gmail.com>

git remote add origin <https://github.com/Shamil-G/REPORTS_GFSS.git>
git branch -M main
git push -u origin main

## Генерим ключ для Linux в папке ~/.ssh/

ssh-keygen -t ed25519 -C "<s.guseeynov@gmail.com>"

## Размещаем строки ниже в файле ~/.ssh/config

## Конфигурация для GitHub

Host github.com
    User git
    HostName github.com
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

## Проверяем подключение к GitHub

ssh -T <git@github.com>

## Проверяем подключение к GitHub

git remote -v

## Изменим протокол запроса с https на git запрос

git remote set-url origin <git@github.com>:Shamil-G/REPORTS_GFSS.git

## Привязка VS Code

### Привязка запуска  Программы аналогично GO

#### Ctrl+K+S - вызываем привязку горячих клавиш

#### Выбираем запуск без отладки

В строке поиска введите: Debug: Start Without Debugging (или если у вас включился русский язык — Запуск без отладки)

#### Жмем Ctrl + Shift + B и Enter - выбрали комбинацию клавиш как в GO

#### Заполняме файл .vscode/launch.json

{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Запуск main_app.py",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/main_app.py",
            "console": "integratedTerminal",
            "internalConsoleOptions": "neverOpen"
        }
    ]
}

#### Заполняем файл keybindings.json

**Варианты открытия файла:**

* **1 Вариант**: Нажмите на **Шестеренку** -> выберите **Keyboard Shortcuts** (Сочетания клавиш). В правом верхнем углу нажмите на иконку документа со стрелкой.
* **2 Вариант**: Перейдите в меню **File** -> **Preferences** -> **Settings**. В правом верхнем углу нажмите на иконку документа. Откроется `settings.json` (настройки внешнего вида, шрифтов и плагинов). Он лежит в одной папке с `keybindings.json`. Нажмите `Ctrl + P`, введите `keybindings.json` и нажмите **Enter**.
* **3 Вариант**: Нажмите комбинацию **`Win + R`**, вставьте путь `%appdata%\Code\User\keybindings.json` и нажмите **Enter** для принудительного открытия файла.

**Что вставить внутрь файла:**

Удалите старое содержимое и вставьте следующий JSON-код:

```json
[
    {
        "key": "ctrl+shift+b",
        "command": "workbench.action.terminal.sendSequence",
        "args": {
            "text": "python main_app.py\u000D"
        },
        "when": "editorTextFocus"
    }
]
```

#### Глобальная установка Go на Linux (для всех пользователей)

Все команды выполняются с правами суперпользователя (**root** или через **sudo**).

**1. Скачивание и распаковка архива**

Перейдите во временную папку, скачайте актуальную версию Go (например, 1.22.0) и распакуйте её в системную директорию `/usr/local`:

#### Глобальная установка Go 1.26 на Oracle Linux

Все команды выполняются с правами суперпользователя (**sudo**).

> ⚠️ **Важно:** Перед выполнением команды `wget` обязательно удалите пробелы вокруг точек в адресе `dl . google . com`!

```bash
cd /tmp

# 1. Скачиваем актуальный архив Go 1.26.0 (УДАЛИТЕ ПРОБЕЛЫ перед запуском!)
wget https://dl.google.com/go/go1.26.0.linux-amd64.tar.gz

# 2. Удаляем старые файлы и распаковываем новую версию
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.26.0.linux-amd64.tar.gz

# 3. Прописываем пути в глобальный профиль
echo 'export PATH=\$PATH:/usr/local/go/bin' | sudo tee -a /etc/profile

# 4. Обновляем сессию терминала
source /etc/profile

# 5. Проверяем, что в системе теперь стоит версия 1.26
go version
```


**2. Настройка глобальных переменных окружения**

Чтобы Go был доступен всем пользователям системы, добавьте пути в файл `/etc/profile`:

```bash
echo 'export PATH=\$PATH:/usr/local/go/bin' | sudo tee -a /etc/profile
```

*Если пользователям также нужен общий путь для устанавливаемых Go-пакетов (GOPATH), выполните:*

```bash
echo 'export GOPATH=\$HOME/go' | sudo tee -a /etc/profile
echo 'export PATH=PATH:GOPATH/bin' | sudo tee -a /etc/profile
```

**3. Применение настроек и проверка**

Чтобы применить изменения без перезагрузки сервера, обновите конфигурацию в текущей сессии:

```bash
source /etc/profile
```

Проверьте корректность установки. Команда должна вернуть версию Go для любого пользователя:

```bash
go version
```


#### Системная настройка Git для всех пользователей сервера

Чтобы имя автора и email были общими для всех учетных записей на сервере (включая `root`), используйте флаг `--system` (требуются права **sudo**):

```bash
# Настройка общего имени автора коммитов
sudo git config --system user.name "Shared Test Account"

# Настройка общего email
sudo git config --system user.email "test-app@example.com"
```

**Полезные системные команды для проверки:**

* Посмотреть настройки уровня всей системы:
  ```bash
  git config --system --list
  ```
* Проверить, какие именно параметры видит конкретный пользователь (команда покажет итоговый приоритет настроек):
  ```bash
  git config --list --show-origin
  ```
