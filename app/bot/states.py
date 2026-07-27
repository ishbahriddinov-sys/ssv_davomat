"""FSM-состояния диалогов бота."""
from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    choosing_language = State()
    waiting_corporate_id = State()
    waiting_phone = State()
    waiting_otp = State()


class TwoFAStates(StatesGroup):
    waiting_code = State()


class CheckStates(StatesGroup):
    waiting_geo_checkin = State()
    waiting_geo_checkout = State()
    waiting_qr = State()


class LeaveStates(StatesGroup):
    choosing_type = State()
    waiting_start = State()
    waiting_end = State()
    waiting_reason = State()


class AdminStates(StatesGroup):
    add_corporate_id = State()
    add_full_name = State()
    add_phone = State()
    add_position = State()
    add_department = State()
