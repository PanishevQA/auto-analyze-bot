from pathlib import Path
from datetime import datetime,timezone
from aiogram import F,Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.types import CallbackQuery,InlineKeyboardButton,InlineKeyboardMarkup,Message

from schemas import (ConditionAssessment,MarketEstimate,PartOffer,PartPriceEstimate,
    PartSearchQuery,PartsStatus,RepairEstimate,VehicleSpec)
from services.manual_parts_provider import ManualBrowserPartsProvider,validate_drom_baza_url
from services.parts_matcher import match_offer
from services.photos import temporary_analysis_directory
from utils.deal_formatters import format_deal_details,format_deal_summary
from utils.messages import answer_long_html
from utils.keyboards import main_menu

router=Router()
class ManualParts(StatesGroup): collecting=State(); confirming=State()

def controls(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Распознать",callback_data="manualparts:extract")],
    [InlineKeyboardButton(text="⬅️ Назад",callback_data="manualparts:back")],
    [InlineKeyboardButton(text="⏭ Пропустить",callback_data="manualparts:skip")],
    [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel"),
     InlineKeyboardButton(text="🏠 Главное меню",callback_data="nav:home")]])

@router.callback_query(F.data.regexp(r"^manualparts:\d+$"))
async def begin(callback:CallbackQuery,state:FSMContext,db,settings):
    calc_id=int(callback.data.split(":",1)[1]); calculation=await db.get_calculation_by_id(calc_id,callback.from_user.id)
    if not calculation: await callback.answer("Расчёт не найден",show_alert=True); return
    queries=calculation.get("parts_query_data") or []
    if not queries: await callback.answer("Нет деталей для поиска",show_alert=True); return
    prior=calculation.get("parts_data") or []
    ready_ids={item.get("defect_id") for item in prior if item.get("status") in {"READY","NOT_REQUIRED"}}
    index=next((i for i,item in enumerate(queries) if item.get("defect_id") not in ready_ids),0)
    await state.set_state(ManualParts.collecting); await state.update_data(manual_calc_id=calc_id,manual_screenshots=[],manual_query_index=index)
    query=queries[index]; url=validate_drom_baza_url(settings.drom_baza_start_url)
    await callback.message.answer(f"🔎 <b>Запчасть {index+1} из {len(queries)}</b>\n"
        f"Необходимо найти: {query.get('part_name','деталь')}\nПоисковая фраза: {query.get('query',query.get('part_name'))}\n"
        "Откройте Drom Базу и отправьте 3–10 скриншотов видимых карточек. Данные будут показаны до включения в расчёт.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть Drom Базу",url=url)],
            [InlineKeyboardButton(text="Отправить ссылки",callback_data="manualparts:links"),
             InlineKeyboardButton(text="Отправить скриншоты",callback_data="manualparts:screens")],
            [InlineKeyboardButton(text="⏭ Пропустить",callback_data="manualparts:skip")],
            [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel"),
             InlineKeyboardButton(text="🏠 Главное меню",callback_data="nav:home")]])); await callback.answer()

@router.callback_query(ManualParts.collecting,F.data.in_({"manualparts:links","manualparts:screens"}))
async def choose_input(callback:CallbackQuery):
    if callback.data.endswith("links"):
        await callback.message.answer("Пришлите 3–10 строк: <code>HTTPS-ссылка | название карточки | текущая цена ₽</code>. "
            "Бот не будет открывать ссылки автоматически.")
    else: await callback.message.answer("Пришлите 3–10 скриншотов выдачи, затем нажмите «Распознать».",reply_markup=controls())
    await callback.answer()

@router.message(ManualParts.collecting,F.text)
async def links(message:Message,state:FSMContext,db):
    rows=[row.strip() for row in (message.text or "").splitlines() if row.strip()]
    if not 3<=len(rows)<=10: await message.answer("Нужно от 3 до 10 строк."); return
    data=await state.get_data(); old=await db.get_calculation_by_id(data["manual_calc_id"],message.from_user.id)
    raw=(old["parts_query_data"] or [])[data["manual_query_index"]]; allowed=set(PartSearchQuery.model_fields)
    query=PartSearchQuery.model_validate({k:v for k,v in raw.items() if k in allowed}); offers=[]
    for row in rows:
        try:
            url,title,price=(part.strip() for part in row.split("|",2)); url=validate_drom_baza_url(url)
            amount=int("".join(c for c in price if c.isdigit()))
            offers.append(match_offer(query,PartOffer(provider="DROM_BAZA_MANUAL",part_name=title,
                condition=query.condition,unit_price_rub=amount,in_stock=True,offer_url=url,
                fetched_at=datetime.now(timezone.utc),source="DROM_BAZA_MANUAL")))
        except (ValueError,TypeError): await message.answer("Не удалось разобрать строки. Проверьте URL | название | цена."); return
    preview="\n".join(f"• {o.part_name}: {o.unit_price_rub} ₽ — {o.match_status.value}" for o in offers)
    await state.update_data(manual_offers=[o.model_dump(mode="json") for o in offers],manual_query=query.model_dump(mode="json"))
    await state.set_state(ManualParts.confirming)
    await message.answer("Проверьте данные:\n"+preview,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить",callback_data="manualparts:confirm")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="manualparts:back")],
        [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="nav:home")]]))

@router.message(ManualParts.collecting,F.photo|F.document)
async def screenshot(message:Message,state:FSMContext):
    item=message.photo[-1] if message.photo else message.document
    mime="image/jpeg" if message.photo else item.mime_type
    if mime not in {"image/jpeg","image/png","image/webp"}: await message.answer("Нужен JPEG, PNG или WebP."); return
    data=await state.get_data(); items=data.get("manual_screenshots",[])
    if item.file_unique_id in {x["unique_id"] for x in items}: return
    if len(items)>=10: await message.answer("Максимум 10 скриншотов."); return
    items.append({"file_id":item.file_id,"unique_id":item.file_unique_id,"mime":mime})
    await state.update_data(manual_screenshots=items)
    await message.answer(f"Скриншотов: {len(items)}",reply_markup=controls())

@router.callback_query(ManualParts.collecting,F.data=="manualparts:extract")
async def extract(callback:CallbackQuery,state:FSMContext,db,parts_agent,settings):
    data=await state.get_data(); shots=data.get("manual_screenshots",[])
    if not 3<=len(shots)<=10: await callback.answer("Добавьте от 3 до 10 скриншотов",show_alert=True); return
    old=await db.get_calculation_by_id(data["manual_calc_id"],callback.from_user.id); raw=(old["parts_query_data"] or [])[data["manual_query_index"]]
    allowed=set(PartSearchQuery.model_fields); query=PartSearchQuery.model_validate({k:v for k,v in raw.items() if k in allowed})
    async with temporary_analysis_directory(old["id"]) as directory:
        paths=[]
        for number,item in enumerate(shots,1):
            remote=await callback.bot.get_file(item["file_id"])
            suffix={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[item["mime"]]
            path=directory/f"shot-{number}{suffix}"
            await callback.bot.download_file(remote.file_path,destination=path); paths.append(path)
        offers=await parts_agent.extract_screenshots(paths,query)
    matched=[]
    for offer in offers:
        if offer.offer_url:
            try: validate_drom_baza_url(str(offer.offer_url))
            except ValueError: continue
        matched.append(match_offer(query,offer))
    preview="\n".join(f"• {offer.part_name}: {offer.unit_price_rub} ₽ — {offer.match_status.value}" for offer in matched) or "Подходящие карточки не распознаны."
    await state.update_data(manual_offers=[o.model_dump(mode="json") for o in matched],manual_query=query.model_dump(mode="json"))
    await state.set_state(ManualParts.confirming)
    await callback.message.answer("Проверьте распознанные данные:\n"+preview,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить",callback_data="manualparts:confirm")],
            [InlineKeyboardButton(text="⬅️ Назад",callback_data="manualparts:back")],
        [InlineKeyboardButton(text="❌ Отменить",callback_data="nav:cancel"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="nav:home")]])); await callback.answer()

@router.callback_query(ManualParts.confirming,F.data=="manualparts:confirm")
async def confirm(callback:CallbackQuery,state:FSMContext,db,deal_engine,repair_catalog,settings,parts_agent):
    data=await state.get_data(); old=await db.get_calculation_by_id(data["manual_calc_id"],callback.from_user.id)
    vehicle=VehicleSpec.model_validate(old["car_data"])
    market_data=old.get("market_data") or {}
    market=MarketEstimate.model_validate(market_data) if market_data.get("source") else None
    repairs=RepairEstimate.model_validate(old["repair_estimate"]); condition=ConditionAssessment.model_validate(old["condition_data"])
    query=PartSearchQuery.model_validate(data["manual_query"]); offers=[PartOffer.model_validate(x) for x in data["manual_offers"]]
    matching={"matching_source":"RULES_FALLBACK","fallback_used":True,"input_offers":len(offers)}
    try: offers,matching=await parts_agent.classify_offers(vehicle,query,offers)
    except Exception: pass
    provider=ManualBrowserPartsProvider(settings.drom_baza_start_url,settings.parts_min_matched_offers)
    quote=provider.normalize_submitted(query,offers).model_copy(update={"query_data":{**query.model_dump(mode="json",exclude={"vin"}),**matching}})
    previous=[PartPriceEstimate.model_validate(item) for item in (old.get("parts_data") or [])]
    quotes=list(previous)
    quote_index=next((i for i,item in enumerate(quotes) if item.defect_id==quote.defect_id),None)
    if quote_index is None: quotes.append(quote)
    else: quotes[quote_index]=quote
    complete=bool(quotes) and all(item.status in {PartsStatus.READY,PartsStatus.NOT_REQUIRED} for item in quotes)
    parts_total=sum(item.selected_price_rub or 0 for item in quotes if item.status is PartsStatus.READY)
    overall=PartsStatus.READY if complete else next((item.status for item in quotes if item.status not in {PartsStatus.READY,PartsStatus.NOT_REQUIRED}),quote.status)
    deal=deal_engine.calculate(asking_price_rub=vehicle.asking_price_rub,market=market,repairs=repairs,
        coverage=condition.coverage,has_blocking_risk=repair_catalog.has_blocking_risk(condition.defects),
        parts_total_rub=parts_total,parts_complete=complete)
    summary=format_deal_summary(vehicle,deal,market); details=format_deal_details(vehicle,market,condition,repairs,deal,quotes)
    await db.complete_analysis(old["id"],parts_data=[item.model_dump(mode="json") for item in quotes],parts_status=overall.value,
        parts_complete=complete,parts_source=quote.provider,parts_quoted_at=quote.fetched_at,
        scores={"deal_result":deal.model_dump(mode="json")},final_report=summary+"\n\n"+details,
        status="COMPLETED" if complete else "PARTIAL")
    await state.clear(); await callback.answer(); await callback.message.answer(summary); await answer_long_html(callback.message,details)
    if not complete:
        remaining=sum(item.status not in {PartsStatus.READY,PartsStatus.NOT_REQUIRED} for item in quotes)
        await callback.message.answer(f"Остались неоценённые детали: {remaining}.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Перейти к следующей детали",callback_data=f"manualparts:{old['id']}")]]))

@router.callback_query(F.data=="manualparts:skip")
async def skip(callback:CallbackQuery,state:FSMContext):
    await state.clear(); await callback.answer(); await callback.message.answer("Оценка запчастей пропущена; экономика остаётся неполной.",reply_markup=main_menu())

@router.callback_query(F.data=="manualparts:back")
async def back(callback:CallbackQuery,state:FSMContext):
    await state.clear(); await callback.answer(); await callback.message.answer("Возврат к отчёту.",reply_markup=main_menu())
