"""`alembic upgrade head` (the Render pre-deploy command) aborts when the
revision graph has several heads, so parallel branches must be merged."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[3]


def test_migrations_have_a_single_head():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"multiple alembic heads, run `alembic merge heads`: {heads}"
