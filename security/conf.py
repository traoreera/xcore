import os

from dotenv import find_dotenv, load_dotenv

from configurations import secure

cfg = secure.Secure(secure.Configure())

load_dotenv(
    dotenv_path=find_dotenv(
        filename=cfg.custom_config["dotenv"], raise_error_if_not_found=True
    )
)


class TokenConfig:
    JWTKEY: str = os.getenv("JWTKEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ISSUER: str = os.getenv("ISSUER")
    ACCESS_TOKEN_EXPIRE_MINUTES: str = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
