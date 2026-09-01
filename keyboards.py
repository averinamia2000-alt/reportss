from aiogram.utils.keyboard import InlineKeyboardBuilder
from projects import PROJECTS

def projects_kb():
    b=InlineKeyboardBuilder()
    for p in PROJECTS: b.button(text=p["name"], callback_data=f"p:{p['name']}")
    b.adjust(2); return b.as_markup()

def cadence_kb(project):
    b=InlineKeyboardBuilder(); b.button(text="📅 Weekly",callback_data=f"c:{project}:w"); b.button(text="🗓 Monthly",callback_data=f"c:{project}:m"); b.button(text="🏠 Главное меню",callback_data="home"); b.adjust(2,1); return b.as_markup()

def type_kb(project):
    b=InlineKeyboardBuilder(); b.button(text="🌐 Глобал",callback_data=f"t:{project}:global"); b.button(text="⚙️ Операционный",callback_data=f"t:{project}:operational"); b.button(text="🏠 Главное меню",callback_data="home"); b.adjust(2,1); return b.as_markup()

def period_kb(project, typ):
    b=InlineKeyboardBuilder(); b.button(text="Эта неделя",callback_data=f"r:{project}:{typ}:0"); b.button(text="Предыдущая",callback_data=f"r:{project}:{typ}:1"); b.button(text="🏠 Главное меню",callback_data="home"); b.adjust(2,1); return b.as_markup()

def after_kb(project, typ=None):
    b=InlineKeyboardBuilder(); b.button(text="📁 Другой проект",callback_data="home")
    if typ: b.button(text="📅 Другой период",callback_data=f"t:{project}:{typ}")
    b.button(text="🏠 Главное меню",callback_data="home"); b.adjust(1); return b.as_markup()
