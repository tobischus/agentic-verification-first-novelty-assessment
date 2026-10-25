"""Add paper_readings (models.PaperReading)."""
from ..backend import models


def upgrade(conn) -> None:
    models.PaperReading.__table__.create(bind=conn, checkfirst=True)
