from decimal import Decimal, InvalidOperation
import secrets

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message)

from services.drom import InvalidDromUrl, ManualDromAdapter
from services.photos import PhotoCollection, PhotoLimitError, PhotoLimits
from schemas import PhotoReference
from utils.formatters import format_summary
from utils.validators import validate_mileage, validate_price, validate_year
from utils.keyboards import BACK,CANCEL,HOME,NEW_ANALYSIS,SKIP,main_menu,navigation
from handlers.navigation import CONTROL_TEXTS

router = Router()


class Questionnaire(StatesGroup):
    source = State(); drom_url = State(); make = State(); model = State(); year = State()
    generation = State(); mileage = State(); price = State(); engine_volume = State()
    fuel_type = State(); horsepower = State(); transmission = State(); drive = State()
    body_type = State(); vin = State(); region = State(); description = State(); photos = State(); confirmation = State()

PREVIOUS={Questionnaire.model.state:Questionnaire.make,Questionnaire.year.state:Questionnaire.model,
    Questionnaire.generation.state:Questionnaire.year,Questionnaire.mileage.state:Questionnaire.generation,
    Questionnaire.price.state:Questionnaire.mileage,Questionnaire.engine_volume.state:Questionnaire.price,
    Questionnaire.fuel_type.state:Questionnaire.engine_volume,Questionnaire.horsepower.state:Questionnaire.fuel_type,
    Questionnaire.transmission.state:Questionnaire.horsepower,Questionnaire.drive.state:Questionnaire.transmission,
    Questionnaire.body_type.state:Questionnaire.drive,Questionnaire.vin.state:Questionnaire.body_type,
    Questionnaire.description.state:Questionnaire.vin,Questionnaire.photos.state:Questionnaire.description}

@router.message(F.text==BACK)
async def go_back(message:Message,state:FSMContext):
    current=await state.get_state(); data=await state.get_data()
    if current==Questionnaire.make.state:
        previous=Questionnaire.drom_url if data.get("source_route")=="DROM" else Questionnaire.source
    else: previous=PREVIOUS.get(current)
    if previous is None:
        await message.answer("Это меню устарело. Откройте главное меню",reply_markup=main_menu()); return
    await state.set_state(previous)
    await render_step(message,state,previous)

@router.message(F.text==SKIP)
async def skip_optional(message:Message,state:FSMContext):
    current=await state.get_state(); transitions={
        Questionnaire.drom_url.state:("source_url",None,Questionnaire.make),Questionnaire.generation.state:("generation",None,Questionnaire.mileage),
        Questionnaire.engine_volume.state:("engine_volume_l",None,Questionnaire.fuel_type),Questionnaire.horsepower.state:("horsepower",None,Questionnaire.transmission),
        Questionnaire.body_type.state:("body_type",None,Questionnaire.vin),Questionnaire.vin.state:("vin",None,Questionnaire.description),
        Questionnaire.description.state:("seller_description",None,Questionnaire.photos)}
    if current not in transitions: await message.answer("Это поле нельзя пропустить."); return
    key,value,next_state=transitions[current]; await state.update_data(**{key:value}); await state.set_state(next_state)
    await render_step(message,state,next_state)

async def render_step(message,state,step):
    data=await state.get_data(); current={k:v for k,v in data.items() if v not in (None,"")}
    if step is Questionnaire.source:
        await message.answer("Выберите источник:",reply_markup=source_keyboard()); return
    if step is Questionnaire.drom_url:
        await message.answer("Отправьте HTTPS-ссылку Drom:",reply_markup=navigation(optional=True)); return
    prompts={Questionnaire.make:"Марка автомобиля",Questionnaire.model:"Модель",Questionnaire.year:"Год выпуска",
        Questionnaire.generation:"Поколение",Questionnaire.mileage:"Пробег, км",Questionnaire.price:"Цена продавца, ₽",
        Questionnaire.engine_volume:"Объём двигателя",Questionnaire.horsepower:"Мощность, л.с.",
        Questionnaire.body_type:"Тип кузова",Questionnaire.vin:"VIN",Questionnaire.description:"Описание продавца"}
    if step is Questionnaire.fuel_type: await message.answer("Тип топлива:",reply_markup=buttons("fuel",["GASOLINE","DIESEL","HYBRID","ELECTRIC","LPG","UNKNOWN"])); return
    if step is Questionnaire.transmission: await message.answer("Коробка:",reply_markup=buttons("trans",["MANUAL","AUTOMATIC","ROBOT","VARIATOR","UNKNOWN"])); return
    if step is Questionnaire.drive: await message.answer("Привод:",reply_markup=buttons("drive",["FWD","RWD","AWD","UNKNOWN"])); return
    if step is Questionnaire.photos: await message.answer(f"Загружено фотографий: {len(data.get('photos',[]))}",reply_markup=photo_keyboard()); return
    key=step.state.rsplit(":",1)[-1]; value=current.get({"price":"asking_price_rub","mileage":"mileage_km","engine_volume":"engine_volume_l"}.get(key,key),"не указано")
    await message.answer(f"{prompts.get(step,'Введите значение')}\nТекущее значение: {value}",reply_markup=navigation(optional=step in {Questionnaire.generation,Questionnaire.engine_volume,Questionnaire.horsepower,Questionnaire.body_type,Questionnaire.vin,Questionnaire.description}))


def buttons(prefix: str, values: list[str]) -> InlineKeyboardMarkup:
    labels={"MANUAL":"Механика","AUTOMATIC":"Автомат","ROBOT":"Робот","VARIATOR":"Вариатор",
        "FWD":"Передний","RWD":"Задний","AWD":"Полный","UNKNOWN":"Не знаю",
        "GASOLINE":"Бензин","DIESEL":"Дизель","HYBRID":"Гибрид","ELECTRIC":"Электро","LPG":"Газ"}
    rows=[[InlineKeyboardButton(text=labels.get(value,value),callback_data=f"{prefix}:{value}")] for value in values]
    rows.extend([[InlineKeyboardButton(text="⬅️ Назад",callback_data="nav:back")],
        [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel"),
         InlineKeyboardButton(text="🏠 Главное меню",callback_data="nav:home")]])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def source_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Есть ссылка Drom",callback_data="source:DROM")],
        [InlineKeyboardButton(text="✍️ Ввести данные вручную",callback_data="source:MANUAL")],
        [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel")]])


def photo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить загрузку", callback_data="photos:done")],
        [InlineKeyboardButton(text="🗑 Удалить последнюю", callback_data="photos:last"),
         InlineKeyboardButton(text="🧹 Очистить", callback_data="photos:clear")],
        [InlineKeyboardButton(text="Продолжить без фото", callback_data="photos:skip")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:back")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="nav:cancel"),
         InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


@router.callback_query(F.data == "analyze")
async def begin(callback: CallbackQuery, state: FSMContext, db, settings) -> None:
    await begin_for_message(callback.message,state,db,callback.from_user.id,settings); await callback.answer()

@router.message(F.text==NEW_ANALYSIS)
async def begin_button(message:Message,state:FSMContext,db,settings):
    await begin_for_message(message,state,db,message.from_user.id,settings)

async def begin_for_message(message,state,db,user_id,settings):
    await state.clear(); await state.set_state(Questionnaire.source)
    user = await db.get_user(user_id)
    await state.update_data(region=user.region if user else "Весь РФ",test_mode=settings.test_mode)
    await message.answer("Выберите источник:",reply_markup=source_keyboard())


@router.callback_query(Questionnaire.source, F.data.startswith("source:"))
async def source(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    await state.update_data(source_mode="MANUAL",source_route=mode, photos=[])
    if mode == "DROM":
        await state.set_state(Questionnaire.drom_url); await callback.message.answer("Отправьте HTTPS-ссылку Drom:",reply_markup=navigation(optional=True))
    else:
        await state.update_data(source_url=None); await ask_make(callback.message, state)
    await callback.answer()


@router.message(Questionnaire.drom_url)
async def drom_url(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip().lower() in {"/skip", "-"}:
        await state.update_data(source_url=None)
        if await _finish_edit(message,state): return
        await ask_make(message,state); return
    try: source_data = await ManualDromAdapter().validate(message.text or "")
    except InvalidDromUrl as error:
        await message.answer(f"❌ {error}. Повторите ссылку:"); return
    await state.update_data(source_url=source_data.source_url)
    if await _finish_edit(message,state): return
    await ask_make(message, state)


async def ask_make(message: Message, state: FSMContext) -> None:
    await state.set_state(Questionnaire.make); await message.answer("Марка автомобиля:",reply_markup=navigation())


async def save_text(message: Message, state: FSMContext, key: str, next_state: State,
                    question: str, optional: bool = False) -> None:
    value = (message.text or "").strip()
    if value in CONTROL_TEXTS or value in {BACK,SKIP}:
        await message.answer("Используйте кнопку навигации, значение не сохранено."); return
    if optional and value.lower() in {"/skip", "не знаю", "unknown", "-"}: value = None
    elif not value or len(value) > 10_000:
        await message.answer("❌ Некорректное значение. Повторите:"); return
    await state.update_data(**{key: value})
    if await _finish_edit(message, state): return
    await state.set_state(next_state); await message.answer(question)

async def _finish_edit(message: Message, state: FSMContext) -> bool:
    data=await state.get_data()
    if not data.get("editing_field"): return False
    await state.update_data(editing_field=None); await show_confirmation(message,state); return True


@router.message(Questionnaire.make)
async def make(message, state): await save_text(message, state, "make", Questionnaire.model, "Модель:")
@router.message(Questionnaire.model)
async def model(message, state): await save_text(message, state, "model", Questionnaire.year, "Год выпуска:")

@router.message(Questionnaire.year)
async def year(message, state):
    try: value = validate_year(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    await state.update_data(year=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.generation); await message.answer("Поколение:",reply_markup=navigation(optional=True))

@router.message(Questionnaire.generation)
async def generation(message, state): await save_text(message,state,"generation",Questionnaire.mileage,"Пробег, км:",True)
@router.message(Questionnaire.mileage)
async def mileage(message, state):
    try: value=validate_mileage(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    await state.update_data(mileage_km=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.price); await message.answer("Цена продавца, ₽:",reply_markup=navigation())
@router.message(Questionnaire.price)
async def price(message, state):
    try: value=validate_price(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    await state.update_data(asking_price_rub=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.engine_volume); await message.answer("Объём двигателя, например 1.6:",reply_markup=navigation(optional=True))
@router.message(Questionnaire.engine_volume)
async def engine_volume(message, state):
    raw=(message.text or "").strip().replace(",", ".")
    if raw.lower() in {"/skip","не знаю","unknown","-"}: value=None
    else:
        try: value=str(Decimal(raw)); assert Decimal("0") < Decimal(raw) <= 20
        except (InvalidOperation, AssertionError): await message.answer("❌ Введите объём 0–20 или /skip:"); return
    await state.update_data(engine_volume_l=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.fuel_type)
    await message.answer("Тип топлива:",reply_markup=buttons("fuel",["GASOLINE","DIESEL","HYBRID","ELECTRIC","LPG","UNKNOWN"]))

@router.callback_query(Questionnaire.fuel_type,F.data.startswith("fuel:"))
async def fuel(callback,state):
    await state.update_data(fuel_type=callback.data.split(":",1)[1])
    if await _finish_edit(callback.message,state): await callback.answer(); return
    await state.set_state(Questionnaire.horsepower)
    await callback.message.answer("Мощность, л.с.:",reply_markup=navigation(optional=True)); await callback.answer()
@router.message(Questionnaire.horsepower)
async def horsepower(message,state):
    raw=(message.text or "").strip(); value=None if raw.lower() in {"/skip","не знаю","unknown","-"} else int(raw) if raw.isdigit() else -1
    if value is not None and not 1 <= value <= 5000: await message.answer("❌ Введите 1–5000 или /skip:"); return
    await state.update_data(horsepower=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.transmission)
    await message.answer("Коробка:",reply_markup=buttons("trans",["MANUAL","AUTOMATIC","ROBOT","VARIATOR","UNKNOWN"]))
@router.callback_query(Questionnaire.transmission,F.data.startswith("trans:"))
async def transmission(callback,state):
    await state.update_data(transmission=callback.data.split(":",1)[1])
    if await _finish_edit(callback.message,state): await callback.answer(); return
    await state.set_state(Questionnaire.drive)
    await callback.message.answer("Привод:",reply_markup=buttons("drive",["FWD","RWD","AWD","UNKNOWN"])); await callback.answer()
@router.callback_query(Questionnaire.drive,F.data.startswith("drive:"))
async def drive(callback,state):
    await state.update_data(drive=callback.data.split(":",1)[1])
    if await _finish_edit(callback.message,state): await callback.answer(); return
    await state.set_state(Questionnaire.body_type)
    await callback.message.answer("Тип кузова:",reply_markup=navigation(optional=True)); await callback.answer()
@router.message(Questionnaire.body_type)
async def body(message,state): await save_text(message,state,"body_type",Questionnaire.vin,"VIN (17 символов) или /skip:",True)
@router.message(Questionnaire.vin)
async def vin(message,state):
    raw=(message.text or "").strip().upper(); value=None if raw.lower() in {"/skip","не знаю","unknown","-"} else raw
    if value and (len(value)!=17 or any(c in "IOQ" or not c.isalnum() for c in value)):
        await message.answer("❌ VIN должен содержать 17 допустимых символов:"); return
    await state.update_data(vin=value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.description); await message.answer("Описание продавца:",reply_markup=navigation(optional=True))
@router.message(Questionnaire.description)
async def description(message,state):
    value=(message.text or "").strip()
    if value in CONTROL_TEXTS or value in {BACK,SKIP}: return
    await state.update_data(seller_description=None if value.lower()=="/skip" else value)
    if await _finish_edit(message,state): return
    await state.set_state(Questionnaire.photos); await message.answer("Загрузите до 20 фотографий.",reply_markup=photo_keyboard())


@router.message(Questionnaire.photos, F.photo | F.document)
async def add_photo(message: Message,state:FSMContext,settings) -> None:
    data=await state.get_data(); collection=PhotoCollection([PhotoReference.model_validate(x) for x in data.get("photos",[])])
    if message.photo:
        item=message.photo[-1]; mime="image/jpeg"; size=item.file_size
    else:
        item=message.document; mime=item.mime_type or ""; size=item.file_size
    try:
        added=collection.add(file_id=item.file_id,unique_id=item.file_unique_id,mime_type=mime,size_bytes=size,
            media_group_id=message.media_group_id,limits=PhotoLimits(settings.max_photos_per_analysis,
            settings.max_photo_size_bytes,settings.max_total_photos_size_bytes))
    except (PhotoLimitError,ValueError) as error: await message.answer(f"❌ {error}"); return
    if added: await state.update_data(photos=collection.dump())
    text=f"Загружено фотографий: {len(collection.photos)} из {settings.max_photos_per_analysis}"
    status_id=data.get("photo_status_message_id")
    if status_id:
        try: await message.bot.edit_message_text(text,chat_id=message.chat.id,message_id=status_id,reply_markup=photo_keyboard())
        except Exception: status_id=None
    if not status_id:
        status=await message.answer(text,reply_markup=photo_keyboard()); await state.update_data(photo_status_message_id=status.message_id)

@router.callback_query(Questionnaire.photos,F.data.startswith("photos:"))
async def photos_control(callback,state):
    action=callback.data.split(":",1)[1]; data=await state.get_data(); collection=PhotoCollection([PhotoReference.model_validate(x) for x in data.get("photos",[])])
    if action=="last": collection.remove_last(); await state.update_data(photos=collection.dump())
    elif action=="clear": collection.clear(); await state.update_data(photos=[])
    elif action=="skip": collection.clear(); await state.update_data(photos=[],editing_field=None); await show_confirmation(callback.message,state)
    elif action=="done": await state.update_data(editing_field=None); await show_confirmation(callback.message,state)
    if action in {"last","clear"}: await callback.message.answer(f"Фотографий: {len(collection.photos)}",reply_markup=photo_keyboard())
    await callback.answer()

async def show_confirmation(message,state):
    data=await state.get_data(); request_id=secrets.token_urlsafe(9); await state.update_data(analysis_request_id=request_id)
    await state.set_state(Questionnaire.confirmation)
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Запустить анализ",callback_data=f"confirm:{request_id}")],[InlineKeyboardButton(text="✏️ Изменить данные",callback_data="edit")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="edit")],[InlineKeyboardButton(text="❌ Отменить",callback_data="cancel")]])
    warning=("🧪 APIpoint работает в тестовом режиме.\nПлатный запрос к APIpoint не выполнится.\n"
             "Запрос к Yandex AI может оставаться платным.\n\n" if data.get("test_mode") else "")
    await message.answer(warning+format_summary(data),reply_markup=keyboard)

@router.callback_query(Questionnaire.confirmation,F.data=="edit")
async def edit_menu(callback,state):
    fields=[("Марка","make"),("Модель","model"),("Год","year"),("Поколение","generation"),
        ("Пробег","mileage"),("Цена","price"),("Двигатель","engine_volume"),("Мощность","horsepower"),
        ("КПП","transmission"),("Топливо","fuel_type"),("Привод","drive"),("Кузов","body_type"),
        ("Регион","region"),("Ссылка","drom_url"),("VIN","vin"),("Описание","description"),("Фотографии","photos")]
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label,callback_data=f"editfield:{key}")]
        for label,key in fields]+[[InlineKeyboardButton(text="Отмена",callback_data="cancel")]])
    await callback.message.answer("Что изменить? Остальные данные сохранятся.",reply_markup=keyboard); await callback.answer()

@router.callback_query(F.data.startswith("editfield:"))
async def edit_field(callback,state):
    key=callback.data.split(":",1)[1]
    mapping={"make":Questionnaire.make,"model":Questionnaire.model,"year":Questionnaire.year,
        "generation":Questionnaire.generation,"mileage":Questionnaire.mileage,"price":Questionnaire.price,
        "engine_volume":Questionnaire.engine_volume,"horsepower":Questionnaire.horsepower,
        "transmission":Questionnaire.transmission,"fuel_type":Questionnaire.fuel_type,"drive":Questionnaire.drive,
        "body_type":Questionnaire.body_type,"region":Questionnaire.region,"drom_url":Questionnaire.drom_url,
        "vin":Questionnaire.vin,"description":Questionnaire.description,"photos":Questionnaire.photos}
    await state.update_data(editing_field=key); await state.set_state(mapping[key])
    if key=="transmission": await callback.message.answer("Коробка:",reply_markup=buttons("trans",["MANUAL","AUTOMATIC","ROBOT","VARIATOR","UNKNOWN"]))
    elif key=="fuel_type": await callback.message.answer("Топливо:",reply_markup=buttons("fuel",["GASOLINE","DIESEL","HYBRID","ELECTRIC","LPG","UNKNOWN"]))
    elif key=="drive": await callback.message.answer("Привод:",reply_markup=buttons("drive",["FWD","RWD","AWD","UNKNOWN"]))
    else: await callback.message.answer("Введите новое значение:")
    await callback.answer()

@router.message(Questionnaire.region)
async def edit_region(message,state): await save_text(message,state,"region",Questionnaire.confirmation,"",False)

@router.message(Command("cancel"))
@router.callback_query(F.data=="cancel")
async def cancel(event,state):
    await state.clear(); target=event.message if isinstance(event,CallbackQuery) else event
    await target.answer("Действие отменено",reply_markup=main_menu())
    if isinstance(event,CallbackQuery): await event.answer()

@router.message(F.text.in_({CANCEL,HOME}))
async def cancel_button(message:Message,state:FSMContext):
    await state.clear(); await message.answer("Главное меню",reply_markup=main_menu())
