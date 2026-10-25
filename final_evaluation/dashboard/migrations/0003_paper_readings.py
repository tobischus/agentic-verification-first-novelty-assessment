"""Add paper_readings: the per-paper "read the submission first" step (models.PaperReading)."""
from ..backend import models


def upgrade(conn) -> None:
    models.PaperReading.__table__.create(bind=conn, checkfirst=True)
