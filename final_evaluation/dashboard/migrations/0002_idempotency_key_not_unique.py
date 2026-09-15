"""Drop the global UNIQUE on final_responses.idempotency_key (keep an index).

Why: the key is only meaningful within one assignment -- see models.FinalResponse. The
global constraint turned a legitimate submission of a DIFFERENT task that reused a key
into a 500, which the live test suite caught.

Written as a portable rebuild (create new table from the current model metadata, copy,
drop, rename) rather than an `ALTER TABLE ... DROP CONSTRAINT`: SQLite cannot drop an
inline column constraint at all, and `ALTER TABLE ... RENAME TO ...` is the one form both
SQLite and PostgreSQL accept.
"""
from sqlalchemy import MetaData, Table, text

from ..backend import models


def upgrade(conn) -> None:
    inspector_tables = conn.dialect.get_table_names(conn)
    if "final_responses" not in inspector_tables:
        # Fresh database: 0001 already created the table from the CURRENT model, which
        # no longer carries the unique constraint. Nothing to rebuild.
        return

    old = models.FinalResponse.__table__
    # A scratch MetaData so the temp table does not collide with the mapped one.
    tmp = Table("final_responses_new", MetaData(),
                *[c._copy() for c in old.columns])
    tmp.create(bind=conn)
    cols = ", ".join(c.name for c in old.columns)
    conn.execute(text(f"INSERT INTO final_responses_new ({cols}) SELECT {cols} FROM final_responses"))
    conn.execute(text("DROP TABLE final_responses"))
    conn.execute(text("ALTER TABLE final_responses_new RENAME TO final_responses"))
