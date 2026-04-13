from sqlalchemy import inspect


def test_required_tables_exist(app_instance):
    from app.infrastructure import db as db_module

    inspector = inspect(db_module.engine)
    tables = set(inspector.get_table_names())

    expected = {
        "users",
        "invites",
        "device_sessions",
        "chats",
        "chat_members",
        "messages",
        "calls",
        "call_signal_events",
    }
    assert expected.issubset(tables)
