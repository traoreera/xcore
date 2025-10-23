import os

from dotenv import find_dotenv, load_dotenv

from config import CfgManager, Configure

cfg = CfgManager(conf=Configure(file="./config.json"))
load_dotenv(dotenv_path=find_dotenv(filename=cfg.cfgdotenv(), raise_error_if_not_found=True))


class Database:
    URL: str = os.getenv("DATA_URL")
