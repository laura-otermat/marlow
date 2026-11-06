import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    platform_admin_user_id = os.getenv("PLATFORM_ADMIN_USER_ID")


settings = Settings()
