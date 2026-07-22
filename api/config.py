import os
from functools import lru_cache


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID: str = os.environ.get("STRIPE_PRICE_ID", "")
    CRON_SECRET: str = os.environ.get("CRON_SECRET", "")
    GASIFAC_PRIVATE_KEY: str = os.environ.get("GASIFAC_PRIVATE_KEY", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
