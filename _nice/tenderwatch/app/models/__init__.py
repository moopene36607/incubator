"""Importing this package registers every ORM model on SQLModel.metadata."""

from app.models.match import Match
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.tender import Tender
from app.models.user import User

__all__ = ["Match", "Profile", "Subscription", "Tender", "User"]
