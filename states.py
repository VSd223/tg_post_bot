from aiogram.fsm.state import State, StatesGroup

class ChannelStates(StatesGroup):
    waiting_for_channel = State()

class PostCreateStates(StatesGroup):
    waiting_for_content = State()
    preview = State()
    waiting_for_buttons = State()
    waiting_for_new_text = State()
    selecting_channel_instant = State()
    selecting_channel_schedule = State()
    waiting_for_publish_time = State()
    waiting_for_auto_delete = State()
    waiting_for_custom_delete_time = State()

class PostEditStates(StatesGroup):
    waiting_for_link = State()
    selecting_from_list = State()
    editing_menu = State()
    waiting_for_new_text = State()
    waiting_for_new_buttons = State()