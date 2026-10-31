import os


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _db_url() -> str:
    url = env("DATABASE_URL", "sqlite:///./leads.db")
    # Render supplies postgres:// ; SQLAlchemy + psycopg3 wants postgresql+psycopg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _db_url()

# Access control: set APP_PASSWORD to protect the whole app with HTTP Basic auth.
APP_USER = env("APP_USER", "mile1")
APP_PASSWORD = env("APP_PASSWORD")

# AI (Claude). Without a key the app falls back to a simple keyword heuristic.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-haiku-5-5")

# Sources
REDDIT_CLIENT_ID = env("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = env("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = env("REDDIT_USER_AGENT", "mile1-leads/0.1 (by mile1.in)")
SERPER_API_KEY = env("SERPER_API_KEY")  # https://serper.dev

# Behaviour
POLL_MINUTES = int(env("POLL_MINUTES", "15"))
MIN_SCORE = int(env("MIN_SCORE", "40"))  # leads below this are discarded
MAX_VARIANTS = int(env("MAX_VARIANTS", "4"))  # query variants searched per source
SEED_DEMO = env("SEED_DEMO", "true").lower() == "true"


def available_sources() -> dict:
    return {
        "hackernews": True,  # Algolia HN API, no key needed
        "reddit": bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET),
        "linkedin": bool(SERPER_API_KEY),  # public posts via Google index
        "web": bool(SERPER_API_KEY),
    }
