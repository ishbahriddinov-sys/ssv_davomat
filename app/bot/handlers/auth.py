"""Авторизация: выбор языка, корпоративный ID, телефон/OTP, привязка Telegram."""
from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import reply
from app.bot.states import AuthStates
from app.core import ratelimit, security
from app.core.enums import NotificationType
from app.db.models import User
from app.i18n import LANG_NAMES, t
from app.services import log_service, notification_service, user_service

router = Router(name="auth")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, db_user: User | None):
    if db_user and db_user.is_verified:
        await message.answer(
            t("already_registered", db_user.language),
            reply_markup=reply.main_menu(db_user),
        )
        return

    await state.clear()
    b = InlineKeyboardBuilder()
    for code, name in LANG_NAMES.items():
        b.button(text=name, callback_data=f"authlang:{code}")
    b.adjust(1)

    # Логотип + приветствие
    logo = Path("logo.png")
    if logo.exists():
        try:
            await message.answer_photo(FSInputFile(logo), caption=t("welcome"))
        except Exception:  # noqa: BLE001
            await message.answer(t("welcome"))
    else:
        await message.answer(t("welcome"))

    await message.answer(t("choose_language"), reply_markup=b.as_markup())
    await state.set_state(AuthStates.choosing_language)


@router.callback_query(AuthStates.choosing_language, F.data.startswith("authlang:"))
async def pick_language(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":", 1)[1]
    await state.update_data(language=code)
    await call.message.answer(t("ask_corporate_id", code))
    await state.set_state(AuthStates.waiting_corporate_id)
    await call.answer()


@router.message(AuthStates.waiting_corporate_id, F.text)
async def enter_corporate_id(
    message: Message, state: FSMContext, session: AsyncSession
):
    data = await state.get_data()
    lang = data.get("language", "ru")

    # Троттлинг: не даём перебирать корпоративные ID/телефоны с одного аккаунта.
    rl_key = f"botauth:{message.from_user.id}"
    blocked, retry = await ratelimit.is_blocked(rl_key)
    if blocked:
        await message.answer(t("corporate_id_not_found", lang))
        return

    user = await user_service.get_by_corporate_id(session, message.text.strip())
    if not user or not user.is_active:
        await ratelimit.register_failure(rl_key)
        await message.answer(t("corporate_id_not_found", lang))
        return

    await state.update_data(user_id=user.id)
    # Отправляем OTP (в реальной системе — по SMS/почте; здесь показываем в логах)
    otp = security.generate_otp()
    await state.update_data(otp=otp)

    await message.answer(
        t("ask_phone", lang), reply_markup=reply.request_phone(lang)
    )
    await state.set_state(AuthStates.waiting_phone)


@router.message(AuthStates.waiting_phone, F.contact)
async def verify_contact(
    message: Message, state: FSMContext, session: AsyncSession
):
    data = await state.get_data()
    lang = data.get("language", "ru")
    contact: Contact = message.contact
    user = await user_service.get_by_id(session, data["user_id"])
    if not user:
        await message.answer(t("error", lang), reply_markup=reply.remove)
        await state.clear()
        return

    # Контакт должен принадлежать самому отправителю. Только контакт, отправленный
    # кнопкой «Поделиться номером», несёт user_id == отправитель. Пересланная карточка
    # чужого контакта (подмена номера ради захвата чужого аккаунта) — отклоняется.
    if contact.user_id is None or contact.user_id != message.from_user.id:
        await message.answer(t("phone_mismatch", lang))
        return

    if not await user_service.verify_phone(user, contact.phone_number):
        await ratelimit.register_failure(f"botauth:{message.from_user.id}")
        await message.answer(t("phone_mismatch", lang))
        return

    # Не позволяем «перепривязать» уже привязанный аккаунт к другому Telegram
    # без участия администратора (защита от угона учётной записи).
    if user.telegram_id and user.telegram_id != message.from_user.id:
        await message.answer(t("phone_mismatch", lang))
        await log_service.log_action(
            session, "auth.rebind_blocked", actor_id=user.id,
            actor_telegram_id=message.from_user.id, entity="user", entity_id=user.id,
        )
        await session.commit()
        return

    # Если у сотрудника роль администратора и включена 2FA — запросим TOTP
    if user.totp_enabled and user.totp_secret:
        await message.answer(t("ask_2fa", lang), reply_markup=reply.remove)
        await state.set_state(AuthStates.waiting_otp)
        await state.update_data(need_2fa=True)
        return

    await _finish_auth(message, state, session, user, lang)


@router.message(AuthStates.waiting_otp, F.text)
async def verify_otp(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lang = data.get("language", "ru")
    user = await user_service.get_by_id(session, data["user_id"])
    if not user:
        await state.clear()
        return

    code = message.text.strip()
    if data.get("need_2fa"):
        if not security.verify_totp(user.totp_secret, code):
            await message.answer(t("twofa_invalid", lang))
            return
    else:
        if code != data.get("otp"):
            await message.answer(t("otp_invalid", lang))
            return

    await _finish_auth(message, state, session, user, lang)


async def _finish_auth(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: str,
):
    await user_service.bind_telegram(session, user, message.from_user.id, lang)
    await ratelimit.clear(f"botauth:{message.from_user.id}")
    await log_service.log_action(
        session,
        "auth.login",
        actor_id=user.id,
        actor_telegram_id=message.from_user.id,
        entity="user",
        entity_id=user.id,
    )
    name = user_service.decrypt_name(user)
    await message.answer(
        t("auth_success", lang, name=name),
        reply_markup=reply.main_menu(user),
    )
    await state.clear()
