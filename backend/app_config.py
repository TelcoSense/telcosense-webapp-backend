import configparser
from datetime import timedelta

config = configparser.ConfigParser()
config.read("config.ini")

# db config
db_user = config["mariadb"]["user"]
db_password = config["mariadb"]["password"]
db_url = config["mariadb"]["url"]
db_name = config["mariadb"]["db_name"]
# connection to the db server
DB_SERVER_CONNECTION_STRING = f"mysql+pymysql://{db_user}:{db_password}@{db_url}"
# connection to the main telcosense_webapp db and the aux dbs (chmi_metadata and cml_metadata)
DB_CONNECTION_STRING = f"mysql+pymysql://{db_user}:{db_password}@{db_url}/{db_name}"
DB_CONNECTION_STRING_WS = (
    f"mysql+pymysql://{db_user}:{db_password}@{db_url}/chmi_metadata"
)
DB_CONNECTION_STRING_CML = (
    f"mysql+pymysql://{db_user}:{db_password}@{db_url}/cml_metadata"
)

# img api config
CHMI_IMG_API = config["api"]["chmi_img_api"]
TELCOSENSE_IMG_API = config["api"]["telcosense_img_api"]

# influxdb config
URL_PUBLIC = config["influxdb"]["url_public"]
TOKEN_PUBLIC_READ = config["influxdb"]["token_public_read"]
URL_INTERNAL = config["influxdb"]["url_internal"]
TOKEN_INTERNAL_READ = config["influxdb"]["token_internal_read"]
ORG = config["influxdb"]["org"]

# paths for telcorain historic calcs
TELCORAIN_REPO_PATH = config["telcorain"]["telcorain_repo_path"]
TELCORAIN_ENV_PATH = config["telcorain"]["telcorain_env_path"]
TELCORAIN_OUT_PATH = config["telcorain"]["telcorain_out_path"]
TELCORAIN_OUT_PATH_JSON = config["telcorain"]["telcorain_out_path_json"]

# active historic calculations limit for a single user
TELCORAIN_MAX_CALCS = int(config["telcorain"]["telcorain_max_calcs"])


# flask app config
class Config:
    SQLALCHEMY_DATABASE_URI = DB_CONNECTION_STRING
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = config["auth"]["jwt_secret_key"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_TOKEN_LOCATION = "cookies"
    JWT_COOKIE_SECURE = True
    SQLALCHEMY_BINDS = {"ws": DB_CONNECTION_STRING_WS, "cml": DB_CONNECTION_STRING_CML}
