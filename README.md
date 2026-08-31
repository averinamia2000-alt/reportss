# TOPS Reports Bot

Telegram-бот для Global / Operational / Monthly отчетов.

## Важно: структура GitHub
Загрузите **все файлы из этой папки прямо в корень репозитория**. Папку `app` создавать не нужно.

Корень должен выглядеть так:

```text
Dockerfile
README.md
config.py
db.py
deadlines.py
keyboards.py
main.py
parser.py
projects.py
requirements.txt
.env.example
.gitignore
```

Railway запускает приложение командой `python main.py` из Dockerfile.

## Variables

- `BOT_TOKEN`
- `DATABASE_URL`
- `SOURCE_CHAT_ID`
- `GLOBAL_THREAD_ID`
- `OPERATIONAL_THREAD_ID`
- `MONTHLY_THREAD_ID`
- `ALLOWED_USER_IDS=8525456105,1651726983`
- `ADMIN_USER_ID`
- `TZ=Europe/Nicosia`
- `LOG_LEVEL=INFO`
- `ENVIRONMENT=production`

## Первый запуск

1. Создайте пустой GitHub repository.
2. В GitHub: Add file → Upload files.
3. Откройте распакованную папку `tops_reports_bot_flat`, выделите все файлы и загрузите их.
4. Подключите repository к Railway.
5. Добавьте PostgreSQL и Variables.
6. Deploy.
7. `/whoami` показывает числовой Telegram user_id.

Не публикуйте `BOT_TOKEN` и `DATABASE_URL` в GitHub.
