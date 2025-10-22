import os
from config import CfgManager,Configure
from dotenv import find_dotenv, load_dotenv




cfg= CfgManager(conf=Configure(file="./config.json"))
load_dotenv(dotenv_path=find_dotenv(filename=cfg.dotenv(), raise_error_if_not_found=True))


class Database:
    URL:str = os.getenv("DATA_URL")