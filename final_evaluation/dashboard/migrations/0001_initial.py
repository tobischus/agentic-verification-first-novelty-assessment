"""Create every table in models.py."""

from ..backend import models


def upgrade(conn) -> None:
    models.Base.metadata.create_all(bind=conn)
