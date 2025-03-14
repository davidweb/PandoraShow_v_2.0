import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "UNE_CLE_SECRETE_LONGUE")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///pandora_show.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
