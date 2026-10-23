import asyncio
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_ID
from database import db

router = Router()


# --- FSM HOLATLARI ---
class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm_send = State()


class CaptionState(StatesGroup):
    waiting_for_caption = State()


class ChannelState(StatesGroup):
    waiting_for_chat_id = State()
    waiting_for_title = State()
    waiting_for_url = State()


class AdminManageState(StatesGroup):
    waiting_for_admin_id = State()


# --- KLAVIATURALAR ---
def get_main_panel_kb(user_id: int) -> InlineKeyboardMarkup:
    """Asosiy admin panel tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔗 Majburiy obuna", callback_data="admin_channels"),
            InlineKeyboardButton(text="✍️ Fayl matni (Caption)", callback_data="admin_caption")
        ]
    ]

    # Faqat Bosh Admin (Owner) adminlarni boshqara oladi
    if user_id == OWNER_ID:
        buttons.append([
            InlineKeyboardButton(text="👥 Adminlarni boshqarish", callback_data="admin_manage")
        ])

    buttons.append([
        InlineKeyboardButton(text="❌ Panelni yopish", callback_data="admin_close")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="admin_menu")]
    ])


def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])


# --- ASOSIY PANEL GA KIRISH ---
@router.message(Command("panel"))
async def cmd_panel(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    if not db.is_admin(user_id):
        await message.reply("⛔ Kechirasiz, sizda admin panelga kirish huquqi yo'q.")
        return

    text = (
        "👑 <b>Admin boshqaruv paneliga xush kelibsiz!</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=get_main_panel_kb(user_id), parse_mode="HTML")


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id

    if not db.is_admin(user_id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    text = (
        "👑 <b>Admin boshqaruv paneliga xush kelibsiz!</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_main_panel_kb(user_id), parse_mode="HTML")


@router.callback_query(F.data == "admin_close")
async def cb_admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()


@router.callback_query(F.data == "admin_cancel")
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Amal bekor qilindi.")
    user_id = callback.from_user.id
    text = "👑 <b>Admin paneli:</b>"
    await callback.message.edit_text(text, reply_markup=get_main_panel_kb(user_id), parse_mode="HTML")


# ==============================================================================
# 1. 📊 STATISTIKA
# ==============================================================================
@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not db.is_admin(callback.from_user.id):
        return

    total_users = db.get_user_count()
    today_users = db.get_today_users()
    channels_count = len(db.get_channels())
    admins_count = len(db.get_admins()) + 1

    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {total_users} ta\n"
        f"⚡ <b>Bugun qo'shilganlar:</b> {today_users} ta\n"
        f"📢 <b>Majburiy obuna kanallari:</b> {channels_count} ta\n"
        f"👑 <b>Adminlar soni:</b> {admins_count} ta\n"
    )
    await callback.message.edit_text(text, reply_markup=get_back_kb(), parse_mode="HTML")


# ==============================================================================
# 2. ✍️ FAYL MATNI (CAPTION / REKLAMA)
# ==============================================================================
@router.callback_query(F.data == "admin_caption")
async def cb_admin_caption(callback: CallbackQuery):
    if not db.is_admin(callback.from_user.id):
        return

    current_caption = db.get_setting("custom_caption")
    preview = current_caption if current_caption else "<i>(Hali o'rnatilmagan - standart holatda)</i>"

    text = (
        "✍️ <b>Yuklab berilgan fayllar ostidagi matn (Caption):</b>\n\n"
        f"<b>Hozirgi matn:</b>\n{preview}\n\n"
        "Ushbu matn har bir yuklab olingan video yoki rasm ostida avtomatik chiqadi."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Yangi matn kiritish", callback_data="caption_set")],
        [InlineKeyboardButton(text="🗑 Matnni o'chirish (tozalash)", callback_data="caption_clear")],
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="admin_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "caption_clear")
async def cb_caption_clear(callback: CallbackQuery):
    if not db.is_admin(callback.from_user.id):
        return

    db.delete_setting("custom_caption")
    await callback.answer("✅ Fayl matni muvaffaqiyatli o'chirildi!", show_alert=True)
    await cb_admin_caption(callback)


@router.callback_query(F.data == "caption_set")
async def cb_caption_set(callback: CallbackQuery, state: FSMContext):
    if not db.is_admin(callback.from_user.id):
        return

    await state.set_state(CaptionState.waiting_for_caption)
    text = (
        "✍️ <b>Yangi matnni yuboring:</b>\n\n"
        "Masalan:\n"
        "<i>Yuklab olindi: @mixdownload_bot\nBizning kanal: @uzb_kanal</i>\n\n"
        "Bekor qilish uchun pastdagi tugmani bosing."
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb(), parse_mode="HTML")


@router.message(CaptionState.waiting_for_caption)
async def process_new_caption(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return

    caption = message.text or message.caption or ""
    if not caption.strip():
        await message.reply("Iltimos, matn yuboring.")
        return

    db.set_setting("custom_caption", caption.strip())
    await state.clear()
    await message.reply(
        "✅ <b>Fayl matni muvaffaqiyatli saqlandi!</b>\n\n"
        f"Yangi matn:\n{caption}",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )


# ==============================================================================
# 3. 🔗 MAJBURIY OBUNA (KANALLAR)
# ==============================================================================
@router.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not db.is_admin(callback.from_user.id):
        return

    channels = db.get_channels()
    text = "🔗 <b>Majburiy obuna kanallari ro'yxati:</b>\n\n"

    if not channels:
        text += "<i>Hozircha hech qanday kanal ulanmagan.</i>\n"
    else:
        for idx, ch in enumerate(channels, 1):
            ch_type = "🔴 Zayavka (Join Request)" if ch['is_request'] else "🟢 Oddiy kanal"
            text += f"<b>{idx}.</b> <a href='{ch['url']}'>{ch['title']}</a>\n"
            text += f"   • Turi: {ch_type}\n"
            text += f"   • ID / Manzil: <code>{ch['chat_id']}</code>\n\n"

    kb_buttons = [
        [
            InlineKeyboardButton(text="➕ Oddiy kanal qo'shish", callback_data="add_ch_regular"),
            InlineKeyboardButton(text="➕ Zayavka kanal qo'shish", callback_data="add_ch_request")
        ]
    ]

    if channels:
        kb_buttons.append([
            InlineKeyboardButton(text="🗑 Kanalni o'chirish", callback_data="delete_ch_menu")
        ])

    kb_buttons.append([
        InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="admin_menu")
    ])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data.in_(["add_ch_regular", "add_ch_request"]))
async def cb_add_channel_start(callback: CallbackQuery, state: FSMContext):
    if not db.is_admin(callback.from_user.id):
        return

    is_request = 1 if callback.data == "add_ch_request" else 0
    await state.update_data(is_request=is_request)
    await state.set_state(ChannelState.waiting_for_chat_id)

    text = (
        "📢 <b>1-qadam: Kanal chat ID yoki @username'sini kiriting</b>\n\n"
        "Masalan: <code>@uzb_kanal</code> yoki <code>-1001234567890</code>\n\n"
        "⚠️ <b>MUHIM:</b> Bot ushbu kanalda <b>Admin</b> bo'lishi va foydalanuvchilarni ko'rish huquqi bo'lishi shart!"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb(), parse_mode="HTML")


@router.message(ChannelState.waiting_for_chat_id)
async def process_channel_chat_id(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return

    chat_id = message.text.strip()
    await state.update_data(chat_id=chat_id)
    await state.set_state(ChannelState.waiting_for_title)

    await message.reply(
        "📝 <b>2-qadam: Kanal uchun tugma nomini kiriting</b>\n\n"
        "Masalan: <i>Bizning rasmiy kanal</i>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )


@router.message(ChannelState.waiting_for_title)
async def process_channel_title(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return

    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(ChannelState.waiting_for_url)

    await message.reply(
        "🔗 <b>3-qadam: Kanalga o'tish havolasini (Link) kiriting</b>\n\n"
        "Masalan: <code>https://t.me/uzb_kanal</code> yoki zayavka link: <code>https://t.me/+join_hash...</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )


@router.message(ChannelState.waiting_for_url)
async def process_channel_url(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return

    url = message.text.strip()
    if not url.startswith("http"):
        await message.reply("Iltimos, to'g'ri link (http:// yoki https:// bilan boshlanadigan) yuboring.")
        return

    data = await state.get_data()
    chat_id = data['chat_id']
    title = data['title']
    is_request = data.get('is_request', 0)

    # Bazaga qo'shish
    db.add_channel(chat_id=chat_id, title=title, url=url, is_request=is_request)
    await state.clear()

    ch_type = "Zayavka kanal" if is_request else "Oddiy kanal"
    await message.reply(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
        f"• Nomi: <b>{title}</b>\n"
        f"• Turi: <b>{ch_type}</b>\n"
        f"• Manzili: {url}",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "delete_ch_menu")
async def cb_delete_ch_menu(callback: CallbackQuery):
    if not db.is_admin(callback.from_user.id):
        return

    channels = db.get_channels()
    if not channels:
        await callback.answer("O'chirish uchun kanallar yo'q.")
        return

    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {ch['title']}", callback_data=f"del_ch_{ch['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_channels")])

    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan kanal ustiga bosing:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("del_ch_"))
async def cb_del_channel(callback: CallbackQuery):
    if not db.is_admin(callback.from_user.id):
        return

    channel_id = int(callback.data.split("_")[2])
    db.delete_channel(channel_id)
    await callback.answer("✅ Kanal o'chirildi!", show_alert=True)
    await cb_admin_channels(callback, None)


# ==============================================================================
# 4. 📢 XABAR YUBORISH (BROADCAST)
# ==============================================================================
@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not db.is_admin(callback.from_user.id):
        return

    await state.set_state(BroadcastState.waiting_for_message)
    text = (
        "📢 <b>Barcha foydalanuvchilarga xabar yuborish:</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring (Matn, Rasm, Video yoki Forward qilingan xabar).\n\n"
        "Xabar barcha bot foydalanuvchilariga yetkaziladi."
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb(), parse_mode="HTML")


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        return

    await state.update_data(broadcast_message_id=message.message_id, broadcast_chat_id=message.chat.id)
    await state.set_state(BroadcastState.confirm_send)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, hammaga yuborilsin", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])
    await message.reply(
        "⚠️ <b>Xabarni barcha foydalanuvchilarga yuborishni tasdiqlaysizmi?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(BroadcastState.confirm_send, F.data == "confirm_broadcast")
async def cb_confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not db.is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    msg_id = data['broadcast_message_id']
    from_chat_id = data['broadcast_chat_id']
    await state.clear()

    user_ids = db.get_all_user_ids()
    total = len(user_ids)

    status_msg = await callback.message.edit_text(
        f"⏳ <b>Xabar yuborilmoqda...</b>\nJami: {total} ta foydalanuvchi.",
        parse_mode="HTML"
    )

    sent = 0
    blocked = 0

    for idx, uid in enumerate(user_ids, 1):
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=msg_id)
            sent += 1
        except Exception:
            blocked += 1

        # Har 20 ta xabarda biroz to'xtab turish (Flood control)
        if idx % 25 == 0:
            await asyncio.sleep(0.5)

    await status_msg.edit_text(
        f"✅ <b>Xabarnoma yakunlandi!</b>\n\n"
        f"• Muvaffaqiyatli yuborildi: <b>{sent}</b> ta\n"
        f"• Yetib bormadi (bloklaganlar): <b>{blocked}</b> ta\n"
        f"• Jami: <b>{total}</b> ta",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )


# ==============================================================================
# 5. 👥 ADMINLARNI BOSHQARISH (FAQAT OWNER UCHUN)
# ==============================================================================
@router.callback_query(F.data == "admin_manage")
async def cb_admin_manage(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Bu bo'lim faqat Bosh Admin uchun!", show_alert=True)
        return

    admins = db.get_admins()
    text = (
        "👥 <b>Adminlar ro'yxati:</b>\n\n"
        f"👑 <b>Bosh admin (Owner):</b> <code>{OWNER_ID}</code>\n\n"
    )

    if not admins:
        text += "<i>Qo'shimcha tayinlangan adminlar yo'q.</i>"
    else:
        text += "<b>Yordamchi adminlar:</b>\n"
        for idx, adm in enumerate(admins, 1):
            text += f"{idx}. ID: <code>{adm['user_id']}</code>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin_start")],
        [InlineKeyboardButton(text="🗑 Adminni o'chirish", callback_data="remove_admin_menu")],
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="admin_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "add_admin_start")
async def cb_add_admin_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return

    await state.set_state(AdminManageState.waiting_for_admin_id)
    await callback.message.edit_text(
        "👤 <b>Yangi adminning Telegram ID raqamini kiriting:</b>\n\n"
        "Masalan: <code>123456789</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )


@router.message(AdminManageState.waiting_for_admin_id)
async def process_add_admin_id(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.reply("Iltimos, faqat raqamlardan iborat Telegram ID kiriting.")
        return

    new_admin_id = int(text)
    db.add_admin(new_admin_id, added_by=OWNER_ID)
    await state.clear()

    await message.reply(
        f"✅ <b>Yangi admin muvaffaqiyatli tayinlandi!</b>\nID: <code>{new_admin_id}</code>",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "remove_admin_menu")
async def cb_remove_admin_menu(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return

    admins = db.get_admins()
    if not admins:
        await callback.answer("O'chirish uchun yordamchi adminlar yo'q.", show_alert=True)
        return

    buttons = []
    for adm in admins:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 ID: {adm['user_id']}", callback_data=f"del_adm_{adm['user_id']}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_manage")])

    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan adminni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("del_adm_"))
async def cb_del_admin(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return

    target_id = int(callback.data.split("_")[2])
    db.remove_admin(target_id)
    await callback.answer("✅ Admin o'chirildi!", show_alert=True)
    await cb_admin_manage(callback, None)
