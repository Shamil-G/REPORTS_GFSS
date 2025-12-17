# AIS_GFSS
# Система отчетности Фонда Python

$ git config --global user.name "Shamil-G"
$ git config --global user.email s.gusseynov@gmail.com

git remote add origin https://github.com/Shamil-G/REPORTS_GFSS.git
git branch -M main
git push -u origin main

# GFSSRegistry
Registry some users's action

git config --global user.name "Shamil-G"
git config --global user.email s.gusseynov@gmail.com

git remote add origin https://github.com/Shamil-G/REPORTS_GFSS.git
git branch -M main
git push -u origin main


# Генерим ключ для Linux в папке ~/.ssh/
 ssh-keygen -t ed25519 -C "s.guseeynov@gmail.com"
# Размещаем строки ниже в файле ~/.ssh/config
# Конфигурация для GitHub
Host github.com
    User git
    HostName github.com
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

# Проверяем подключение к GitHub
ssh -T git@github.com

# Проверяем подключение к GitHub
git remote -v

# Изменим протокол запроса с https на git запрос
git remote set-url origin git@github.com:Shamil-G/REPORTS_GFSS.git