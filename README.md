# TOPS Reports Bot

Telegram-бот для Global / Operational / Monthly отчетов.

## Что добавлено

- Global-отчеты разбираются на структурированные метрики: GGR, Deposits, Withdrawals, Withdrawal Rate, FD, InOut; дополнительные метрики — Registrations, Paid Users, RD, Bonus Rate.
- Метрики Traffic / Partners хранятся отдельно от основных.
- История метрик сохраняется в PostgreSQL.
- Risk engine присваивает проектам 🟢 / 🟡 / 🔴 по фиксированным правилам.

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

