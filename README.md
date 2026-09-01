# TOPS Reports Bot

Telegram-бот для Global / Operational / Monthly отчетов и еженедельной аналитической сводки.

## Что добавлено

- Global-отчеты разбираются на структурированные метрики: GGR, Deposits, Withdrawals, Withdrawal Rate, FD, InOut; дополнительные метрики — Registrations, Paid Users, RD, Bonus Rate.
- Метрики Traffic / Partners хранятся отдельно от основных.
- История метрик сохраняется в PostgreSQL.
- Risk engine присваивает проектам 🟢 / 🟡 / 🔴 по фиксированным правилам.
- `/digest` — ручная генерация сводки (только ADMIN_USER_ID).
- По понедельникам в 11:00 Europe/Nicosia сводка отправляется пользователям из `DIGEST_USER_IDS`.
- Если `DIGEST_USER_IDS` пуст, сводка идет только `ADMIN_USER_ID`.

## Railway Variables

- `BOT_TOKEN`
- `DATABASE_URL`
- `SOURCE_CHAT_ID=-1002640153163`
- `GLOBAL_THREAD_ID=869`
- `OPERATIONAL_THREAD_ID=3`
- `MONTHLY_THREAD_ID=2`
- `ALLOWED_USER_IDS=8525456105,1651726983`
- `ADMIN_USER_ID=<ваш numeric Telegram ID>`
- `DIGEST_USER_IDS=<numeric IDs через запятую>`
- `TZ=Europe/Nicosia`
- `LOG_LEVEL=INFO`

### Безопасный запуск сводки

На первом этапе укажите в `DIGEST_USER_IDS` только свой numeric Telegram ID. После проверки качества добавьте ID Анны через запятую.

## Важное ограничение исторического backfill

Старая версия бота сохраняла Telegram message ID, но не текст отчета. Telegram Bot API не дает боту произвольно скачать старую историю группы по message ID. Поэтому структурированная история автоматически начинает накапливаться после деплоя этой версии. Старые периоды можно добавить позже отдельным импортом/повторной подачей отчетов.
