from sqlmodel import Session, create_engine
from app.component.environment import env

database_url = env("database_url", "sqlite:///./local.db")
engine_kwargs = {
    "echo": True if env("debug") == "on" else False,
}
if not database_url.startswith("sqlite"):
    engine_kwargs["pool_size"] = 36

engine = create_engine(
    database_url,
    **engine_kwargs,
)


def session_make():
    return Session(engine)


def session():
    with Session(engine) as session:
        yield session
