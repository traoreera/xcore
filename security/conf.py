import os
from config import Secure, Configure
from dotenv import load_dotenv, find_dotenv

cfg = Secure(conf=Configure(file="./config.json"))

load_dotenv(dotenv_path=find_dotenv(filename=cfg.dotenv(), raise_error_if_not_found=True))

class TokenConfig:
    JWTKEY:str = os.getenv("JWTKEY")
    ALGORITHM:str = os.getenv("ALGORITHM")
    ISSUER:str = os.getenv("ISSUER")
    ACCESS_TOKEN_EXPIRE_MINUTES:str = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))