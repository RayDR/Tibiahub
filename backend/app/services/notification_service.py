from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.guild_management import GuildManagementGrant
from app.models.raffle import InternalNotification, Raffle, RaffleManagerGrant
from app.models.user import User
from app.models.user_character import UserCharacter
from app.services.guild_authorization_service import LEADER_RANKS
from app.services.guild_roster_service import normalize_guild_identity


class NotificationService:
    @staticmethod
    def emit_users(db: Session, recipients: list[User], notification_type: str, event_key: str, *, guild_name: str | None, deep_link: str, payload: dict | None = None) -> None:
        for recipient in {user.id: user for user in recipients if user and user.is_active}.values():
            dedupe = f"{event_key}:user:{recipient.id}"
            if db.query(InternalNotification.id).filter(InternalNotification.recipient_user_id == recipient.id, InternalNotification.deduplication_key == dedupe).first():
                continue
            db.add(InternalNotification(
                recipient_user_id=recipient.id, guild_name=guild_name, raffle_id=None,
                notification_type=notification_type,
                title_key=f"notifications.types.{notification_type}.title",
                message_key=f"notifications.types.{notification_type}.message",
                interpolation=payload or {}, deep_link=deep_link, deduplication_key=dedupe,
            ))

    @staticmethod
    def recipients(db: Session, raffle: Raffle, *, include_managers: bool = True) -> list[User]:
        manager_ids: set[int] = set()
        if include_managers:
            manager_ids.update(row.user_id for row in db.query(GuildManagementGrant).filter(
                GuildManagementGrant.normalized_guild_name == normalize_guild_identity(raffle.guild_name),
                GuildManagementGrant.capability == "raffles.manage",
                GuildManagementGrant.revoked_at.is_(None),
            ))
            manager_ids.update(row.user_id for row in db.query(RaffleManagerGrant).filter(
                RaffleManagerGrant.raffle_id == raffle.id, RaffleManagerGrant.revoked_at.is_(None)
            ))
        leader_ids = {
            row.user_id for row in db.query(UserCharacter).filter(
                UserCharacter.ownership_status == "verified",
                UserCharacter.guild_name.ilike(raffle.guild_name),
            ).all()
            if (row.guild_rank or "").strip().casefold() in LEADER_RANKS
        }
        recipients = manager_ids | leader_ids
        return db.query(User).filter(
            User.is_active.is_(True),
            (User.is_superuser.is_(True)) | (User.id.in_(recipients)),
        ).all()

    @staticmethod
    def emit(db: Session, raffle: Raffle, notification_type: str, event_key: str, *, payload: dict | None = None, include_managers: bool = True) -> None:
        for recipient in NotificationService.recipients(db, raffle, include_managers=include_managers):
            if db.query(InternalNotification.id).filter(
                InternalNotification.recipient_user_id == recipient.id,
                InternalNotification.deduplication_key == event_key,
            ).first():
                continue
            db.add(InternalNotification(
                recipient_user_id=recipient.id, guild_name=raffle.guild_name, raffle_id=raffle.id,
                notification_type=notification_type,
                title_key=f"notifications.types.{notification_type}.title",
                message_key=f"notifications.types.{notification_type}.message",
                interpolation={"raffle": raffle.title, "test": raffle.purpose == "test", **(payload or {})},
                deep_link=f"/guild/raffle?raffle={raffle.id}", deduplication_key=event_key,
            ))

    @staticmethod
    def mark_read(notification: InternalNotification) -> None:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
