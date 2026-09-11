"""
Portable JSON type.

Production runs on PostgreSQL and should use real JSONB (indexable, efficient).
Tests run against SQLite for speed/no external dependency, which has no JSONB.
`JSON().with_variant(JSONB(), "postgresql")` gives us JSONB on Postgres and
falls back to generic JSON everywhere else, from a single column definition.
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

PortableJSON = JSON().with_variant(JSONB(), "postgresql")
