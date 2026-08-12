from datetime import UTC, datetime
from uuid import uuid4

from vitalstream_common.schemas import Role, User


def test_user_schema_round_trip():
    user = User(
        id=uuid4(),
        email="patient@example.com",
        role=Role.PATIENT,
        created_at=datetime.now(UTC),
    )

    assert User.model_validate(user.model_dump()) == user
