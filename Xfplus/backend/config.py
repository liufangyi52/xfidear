from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "张家界·智瞳应急平台"
    weather_api_key: str = Field("", alias="WEATHER_API_KEY")
    amap_server_key: str = Field("", alias="AMAP_SERVER_KEY")
    amap_weather_key: str = Field("", alias="AMAP_WEATHER_KEY")
    iflytek_appid: str = Field("", alias="IFLYTEK_APPID")
    iflytek_api_key: str = Field("", alias="IFLYTEK_API_KEY")
    iflytek_api_secret: str = Field("", alias="IFLYTEK_API_SECRET")
    iflytek_model: str = Field("generalv3", alias="IFLYTEK_MODEL")
    iflytek_http_base_url: str = Field("https://spark-api-open.xf-yun.com/v1", alias="IFLYTEK_HTTP_BASE_URL")
    dashscope_api_key: str = Field("", alias="DASHSCOPE_API_KEY")
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")
    fallback_llm_type: str = Field("mock", alias="FALLBACK_LLM_TYPE")
    frontend_origin: str = Field("http://localhost:5173", alias="FRONTEND_ORIGIN")
    qweather_location_id: str = Field("101251101", alias="QWEATHER_LOCATION_ID")
    ai_timeout_seconds: int = Field(15, alias="AI_TIMEOUT_SECONDS")
    database_url: str = Field(f"sqlite:///{BASE_DIR / 'data' / 'app.db'}", alias="DATABASE_URL")

    @property
    def cors_origins(self) -> List[str]:
        origins = {"http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5176", self.frontend_origin}
        return [origin for origin in origins if origin]

    @property
    def cors_origin_regex(self) -> str:
        return r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(:\d+)?$"


@lru_cache
def get_settings() -> Settings:
    return Settings()
