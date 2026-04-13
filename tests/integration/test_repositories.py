from datetime import UTC, datetime, timedelta

from app.infrastructure.repositories import (
    ChatRepository,
    InviteRepository,
    MessageRepository,
    SessionRepository,
    UserRepository,
)


def test_repositories_basic_flow(app_instance):
    from app.infrastructure import db as db_module

    session_local = db_module.SessionLocal
    db = session_local()
    try:
        user_repo = UserRepository(db)
        invite_repo = InviteRepository(db)
        session_repo = SessionRepository(db)
        chat_repo = ChatRepository(db)
        message_repo = MessageRepository(db)

        invite = invite_repo.create(
            code="REPO-INVITE",
            created_by=None,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
            max_uses=1,
        )
        assert invite.code == "REPO-INVITE"

        user = user_repo.create(username="repo-user", display_name="Repo", password_hash="hash")
        assert user.id > 0

        session = session_repo.create(user_id=user.id, refresh_token_hash="hash1", user_agent="pytest", ip="127.0.0.1")
        assert session.id > 0
        session_repo.revoke(session.id)

        chat = chat_repo.create_chat(chat_type="group", title="RepoChat", created_by=user.id)
        chat_repo.add_member(chat.id, user.id, role="owner")
        assert chat_repo.is_member(chat.id, user.id)

        message = message_repo.create_message(
            chat_id=chat.id,
            sender_id=user.id,
            message_type="text",
            text="hello",
            status="sent",
        )
        assert message.id > 0
        updated = message_repo.update_status(message.id, "read")
        assert updated is not None
        assert updated.status == "read"
    finally:
        db.close()
