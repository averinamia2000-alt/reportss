import asyncio, logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import settings
from db import init_db, Session, Report, ReportMessage
from parser import detect_project, parse_period
from projects import BY_NAME, PROJECTS
from keyboards import projects_kb, cadence_kb, type_kb, period_kb, after_kb
from deadlines import weekly_period, monthly_period, deadline_for, missing_projects, fmt_period
from analytics import upsert_analysis, build_digest

router=Router()

def allowed(uid): return uid in settings.allowed_user_ids

def rtype(thread):
    return {settings.global_thread_id:"global",settings.operational_thread_id:"operational",settings.monthly_thread_id:"monthly"}.get(thread)

def original_url(chat_id, message_id):
    s=str(chat_id)
    if s.startswith("-100"): return f"https://t.me/c/{s[4:]}/{message_id}"
    return None

async def deny(event):
    if isinstance(event, Message): await event.answer("⛔ У вас нет доступа к этому боту.")
    else: await event.answer("Нет доступа", show_alert=True)


async def send_missing_digest(report_type: str):
    now=datetime.now(ZoneInfo(settings.timezone))
    if report_type == "monthly":
        ps,pe=monthly_period(now)
    else:
        ps,pe=weekly_period(report_type,now)
    missing=await missing_projects(report_type,ps,pe)
    if not missing:
        text=f"✅ Все отчеты получены: {report_type} · {fmt_period(ps,pe)}"
    else:
        label={"global":"🌐 Глобал","operational":"⚙️ Операционный","monthly":"🗓 Monthly"}[report_type]
        lines=[f"❌ <b>Не получены отчеты</b>",f"{label} · {fmt_period(ps,pe)}",""]
        for p in missing:
            lines.append(f"• <b>{p['name']}</b> — {p['head']} @{p['head_username']}")
        lines.append(f"\nПолучено: {len(PROJECTS)-len(missing)}/{len(PROJECTS)}")
        text="\n".join(lines)
    if settings.admin_user_id:
        await bot.send_message(settings.admin_user_id,text,parse_mode="HTML")
    else:
        logging.warning("ADMIN_USER_ID is not set; missing digest: %s", text)

async def send_portfolio_digest():
    now=datetime.now(ZoneInfo(settings.timezone))
    ps,pe=weekly_period("global",now)
    text=await build_digest(ps,pe)
    recipients=settings.digest_user_ids or ({settings.admin_user_id} if settings.admin_user_id else set())
    if not recipients:
        logging.warning("DIGEST_USER_IDS/ADMIN_USER_ID are not set; portfolio digest was not sent")
        return
    for uid in recipients:
        try:
            # Telegram limits a message to 4096 chars. Keep logical chunks readable.
            chunks=[]
            current=""
            for line in text.split("\n"):
                candidate=(current+"\n"+line).strip()
                if len(candidate)>3900 and current:
                    chunks.append(current); current=line
                else:
                    current=candidate
            if current: chunks.append(current)
            for chunk in chunks:
                await bot.send_message(uid,chunk,parse_mode="HTML")
        except Exception:
            logging.exception("portfolio digest send failed for user %s",uid)

async def setup_scheduler():
    scheduler=AsyncIOScheduler(timezone=settings.timezone)
    # Cyprus local time. Small 1-minute delay lets reports arriving exactly at deadline be committed first.
    scheduler.add_job(send_missing_digest,"cron",day_of_week="tue",hour=20,minute=1,args=["operational"],id="missing_operational",replace_existing=True)
    scheduler.add_job(send_missing_digest,"cron",day_of_week="fri",hour=20,minute=1,args=["global"],id="missing_global",replace_existing=True)
    scheduler.add_job(send_missing_digest,"cron",day=4,hour=12,minute=1,args=["monthly"],id="missing_monthly",replace_existing=True)
    # Monday 11:00 Cyprus: Global Portfolio Health for the most recent Friday report period.
    scheduler.add_job(send_portfolio_digest,"cron",day_of_week="mon",hour=11,minute=0,id="portfolio_digest",replace_existing=True)
    scheduler.start()
    return scheduler

@router.message(CommandStart())
async def start(m:Message):
    if not allowed(m.from_user.id): return await deny(m)
    await m.answer("Выберите проект 👇", reply_markup=projects_kb())


@router.message(Command("missing"))
async def missing_cmd(m:Message):
    if m.from_user.id != settings.admin_user_id: return await deny(m)
    parts=(m.text or "").split()
    typ=parts[1].lower() if len(parts)>1 else "global"
    aliases={"глобал":"global","global":"global","операционный":"operational","operational":"operational","monthly":"monthly","месячный":"monthly"}
    typ=aliases.get(typ)
    if not typ:
        return await m.answer("Использование: /missing global | operational | monthly")
    now=datetime.now(ZoneInfo(settings.timezone))
    ps,pe=monthly_period(now) if typ=="monthly" else weekly_period(typ,now)
    missing=await missing_projects(typ,ps,pe)
    label={"global":"🌐 Глобал","operational":"⚙️ Операционный","monthly":"🗓 Monthly"}[typ]
    if not missing:
        return await m.answer(f"✅ {label}: все {len(PROJECTS)} отчетов получены за {fmt_period(ps,pe)}")
    lines=[f"{label} · {fmt_period(ps,pe)}",f"❌ Нет {len(missing)} из {len(PROJECTS)}:",""]
    lines += [f"• <b>{p['name']}</b> — {p['head']} @{p['head_username']}" for p in missing]
    await m.answer("\n".join(lines),parse_mode="HTML")

@router.message(Command("whoami"))
async def whoami(m:Message): await m.answer(f"Ваш Telegram user_id: <code>{m.from_user.id}</code>", parse_mode="HTML")

@router.message(Command("digest"))
async def digest_cmd(m:Message):
    if m.from_user.id != settings.admin_user_id: return await deny(m)
    now=datetime.now(ZoneInfo(settings.timezone))
    ps,pe=weekly_period("global",now)
    text=await build_digest(ps,pe)
    for chunk_start in range(0,len(text),3900):
        await m.answer(text[chunk_start:chunk_start+3900],parse_mode="HTML")

@router.callback_query(F.data=="home")
async def home(c:CallbackQuery):
    if not allowed(c.from_user.id): return await deny(c)
    await c.message.edit_text("Выберите проект 👇",reply_markup=projects_kb()); await c.answer()

@router.callback_query(F.data.startswith("p:"))
async def project(c:CallbackQuery):
    if not allowed(c.from_user.id): return await deny(c)
    p=c.data.split(":",1)[1]; await c.message.edit_text(f"📁 {p}\nЧто показать?",reply_markup=cadence_kb(p)); await c.answer()

@router.callback_query(F.data.startswith("c:"))
async def cadence(c:CallbackQuery):
    if not allowed(c.from_user.id): return await deny(c)
    _,p,kind=c.data.split(":")
    if kind=="w": await c.message.edit_text(f"📁 {p}\nВыберите тип weekly-отчета:",reply_markup=type_kb(p))
    else: await send_report(c.message.chat.id,p,"monthly",0); await c.answer(); return
    await c.answer()

@router.callback_query(F.data.startswith("t:"))
async def typ(c:CallbackQuery):
    if not allowed(c.from_user.id): return await deny(c)
    _,p,t=c.data.split(":"); await c.message.edit_text(f"📁 {p}\nВыберите период:",reply_markup=period_kb(p,t)); await c.answer()

@router.callback_query(F.data.startswith("r:"))
async def report_cb(c:CallbackQuery):
    if not allowed(c.from_user.id): return await deny(c)
    _,p,t,offset=c.data.split(":"); await send_report(c.message.chat.id,p,t,int(offset)); await c.answer()

async def send_report(chat_id, project, typ, offset):
    async with Session() as s:
        q=select(Report).where(Report.project==project,Report.report_type==typ).order_by(Report.period_end.desc().nullslast(),Report.received_at.desc()).offset(offset).limit(1)
        rep=(await s.execute(q)).scalar_one_or_none()
        if not rep:
            head=BY_NAME[project]
            await bot.send_message(chat_id,f"😔 Пока не нашел {'месячный' if typ=='monthly' else typ} отчет по <b>{project}</b>.\nЗа отчетом можно обратиться к {head['head']} @{head['head_username']}.",parse_mode="HTML",reply_markup=after_kb(project, typ if typ!='monthly' else None)); return
        label={"global":"🌐 Глобал","operational":"⚙️ Операционный","monthly":"🗓 Monthly"}[typ]
        period = f"{rep.period_start:%d.%m.%Y} — {rep.period_end:%d.%m.%Y}" if rep.period_start and rep.period_end else "последний доступный"
        url=original_url(rep.source_chat_id,rep.first_message_id)
        kb=None
        if url: kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Открыть оригинал",url=url)]])
        await bot.send_message(chat_id,f"{label} · <b>{project}</b> · {period}",parse_mode="HTML",reply_markup=kb)
        msgs=(await s.execute(select(ReportMessage).where(ReportMessage.report_id==rep.id).order_by(ReportMessage.position))).scalars().all()
        for rm in msgs:
            try: await bot.copy_message(chat_id=chat_id,from_chat_id=rep.source_chat_id,message_id=rm.message_id)
            except Exception: logging.exception("copy_message failed")
        await bot.send_message(chat_id,"Что дальше?",reply_markup=after_kb(project, typ if typ!='monthly' else None))

@router.message()
async def source(m:Message):
    # Temporary discovery log: lets us learn SOURCE_CHAT_ID and message_thread_id
    # before those values are configured in Railway.
    if m.chat.type in ("group", "supergroup"):
        logging.info(
            "TELEGRAM DEBUG | chat_id=%s | thread_id=%s | message_id=%s | text=%r",
            m.chat.id,
            m.message_thread_id,
            m.message_id,
            (m.text or m.caption or "")[:100],
        )

    typ=rtype(m.message_thread_id)
    if m.chat.id != settings.source_chat_id or not typ:
        return

    logging.info("source chat=%s thread=%s message=%s",m.chat.id,m.message_thread_id,m.message_id)
    text=m.text or m.caption or ""
    project=detect_project(text)
    async with Session() as s:
        if project:
            ps,pe=parse_period(text,m.date.astimezone(ZoneInfo(settings.timezone)).date())
            rep=Report(project=project,report_type=typ,period_start=ps,period_end=pe,source_chat_id=m.chat.id,source_thread_id=m.message_thread_id,first_message_id=m.message_id,sender_id=m.from_user.id if m.from_user else None,sender_username=m.from_user.username if m.from_user else None,received_at=m.date)
            s.add(rep); await s.flush(); report_id=rep.id; s.add(ReportMessage(report_id=rep.id,message_id=m.message_id,position=0)); await s.commit()
            if typ == "global" and text:
                await upsert_analysis(report_id,text,replace=True)
            logging.info("indexed %s %s %s",project,typ,pe)
        else:
            q=select(Report).where(Report.source_chat_id==m.chat.id,Report.source_thread_id==m.message_thread_id).order_by(Report.received_at.desc()).limit(1)
            rep=(await s.execute(q)).scalar_one_or_none()
            if rep:
                pos=(await s.execute(select(func.count()).select_from(ReportMessage).where(ReportMessage.report_id==rep.id))).scalar_one()
                report_id=rep.id
                s.add(ReportMessage(report_id=rep.id,message_id=m.message_id,position=pos)); await s.commit()
                if rep.report_type == "global" and text:
                    await upsert_analysis(report_id,text)

async def main():
    global bot
    logging.basicConfig(level=getattr(logging,settings.log_level.upper(),logging.INFO))
    if not settings.bot_token or not settings.database_url: raise RuntimeError("BOT_TOKEN and DATABASE_URL are required")
    await init_db(); bot=Bot(settings.bot_token); await setup_scheduler(); dp=Dispatcher(); dp.include_router(router)
    logging.info("bot started")
    await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
