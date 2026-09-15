"""Create every table in models.py. See dashboard/backend/db.py for why this is a Python
function rather than a `.sql` file (portability across SQLite and PostgreSQL)."""
from ..backend import models


def upgrade(conn) -> None:
    models.Base.metadata.create_all(bind=conn)
