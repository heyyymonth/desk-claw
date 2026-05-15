import pytest

from app.db.session import Database


def test_database_accepts_sqlite_urls(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'deskclaw.db'}")

    assert database.dialect == "sqlite"


def test_database_accepts_postgres_urls():
    database = Database("postgres://desk:secret@localhost:5432/desk_ai")

    assert database.dialect == "postgres"
    assert database.database_url == "postgresql://desk:secret@localhost:5432/desk_ai"


def test_database_rejects_unsupported_urls():
    with pytest.raises(ValueError, match="DATABASE_URL must start"):
        Database("mysql://desk:secret@localhost/desk_ai")
