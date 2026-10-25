"""Drop the global UNIQUE on final_responses.idempotency_key (keep an index)."""
from sqlalchemy import MetaData, Table, text

from ..backend import models


def upgrade(conn) -> None:
    inspector_tables = conn.dialect.get_table_names(conn)
    if "final_responses" not in inspector_tables:
        return

    old = models.FinalResponse.__table__
    tmp = Table("final_responses_new", MetaData(),
                *[c._copy() for c in old.columns])
    tmp.create(bind=conn)
    cols = ", ".join(c.name for c in old.columns)
    conn.execute(text(f"INSERT INTO final_responses_new ({cols}) SELECT {cols} FROM final_responses"))
    conn.execute(text("DROP TABLE final_responses"))
    conn.execute(text("ALTER TABLE final_responses_new RENAME TO final_responses"))
