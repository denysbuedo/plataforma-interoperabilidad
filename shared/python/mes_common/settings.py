from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by service processes."""

    service_name: str
    service_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    oidc_issuer_url: str = "https://identidad.reduniv.edu.cu/realms/interoperabilidad"
    oidc_jwks_url: str | None = None
    oidc_public_key_file: str | None = None
    oidc_audience: str = "mes-api"
    oidc_swagger_client_id: str = "api-swagger"
    persons_oidc_issuer_url: str | None = None
    persons_oidc_client_id: str | None = None
    persons_oidc_redirect_uri: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 25
    smtp_tls_server_name: str | None = None
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None
    smtp_timeout_seconds: float = 10.0
    smtp_starttls: bool = True
    smtp_tls_reject_unauthorized: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings(service_name: str) -> Settings:
    return Settings(service_name=service_name)
