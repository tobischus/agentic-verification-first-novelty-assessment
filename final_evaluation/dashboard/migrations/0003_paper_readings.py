"""Add paper_readings: the per-paper "read the submission first" step (models.PaperReading).

A fresh database already has the table -- 0001 creates every table of the CURRENT model --
so this only creates it where it is missing.
"""
from ..backend import models


def upgrade(conn) -> None:
    models.PaperReading.__table__.create(bind=conn, checkfirst=True)
