DB_NAME = "telcosense_webapp"
DB_SERVER_CONNECTION_STRING = "mysql+pymysql://root:pswd123@localhost:3307"


class Config:
    SQLALCHEMY_DATABASE_URI = f"{DB_SERVER_CONNECTION_STRING}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = "jwt_secret_key"
    JWT_TOKEN_LOCATION = "cookies"
    JWT_COOKIE_SECURE = False
