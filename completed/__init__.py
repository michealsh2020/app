import logging
import datetime as dt
import json
import os
import re
import struct
import azure.functions as func
import pyodbc

################################
#  Environment variables
################################
root = os.path.abspath(os.path.curdir)
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING').upper()
MSSQL_SERVER_FQDN = os.environ["MSSQL_SERVER_FQDN"]
MSSQL_DATABASE_NAME = os.environ["MSSQL_DATABASE_NAME"]
MSSQL_DATABASE_USER = os.environ["MSSQL_DATABASE_USER"]
MSSQL_DATABASE_PASSWD = os.environ["MSSQL_DATABASE_PASSWD"]

USER_BASIC_LICENSE_TYPE = 1
USER_PRO_LICENSE_TYPE = 2

################################
#  Setup logger
################################
logging.basicConfig()
logger = logging.getLogger("update_user")
logger.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('[%(levelname)s] %(message)s')
sh = logging.StreamHandler()
sh.setFormatter(log_formatter)
sh.setLevel(LOG_LEVEL)
logger.addHandler(sh)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Executing ' 'fn_deactivate/activate_user' ' HttpTrigger')

    try:
        req_body = req.get_json()
        logger.debug(req_body)
        res, code = user_deactivate_and_activate_sync_webhook(req_body)
        return func.HttpResponse(res, status_code=code)
    except ValueError:
        return func.HttpResponse("Invalid data recieved", status_code=400)


def user_deactivate_and_activate_sync_webhook(data):
    logger.debug('User Data deactivate/activate Sync Method')

    try:
        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER=tcp:{MSSQL_SERVER_FQDN};DATABASE={MSSQL_DATABASE_NAME};UID={MSSQL_DATABASE_USER};PWD={MSSQL_DATABASE_PASSWD}'
        logger.debug(f'Connection string: "{connection_string}"')

        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
    except pyodbc.Error as ex:
        logging.error(ex.args[1])
        return json.dumps(build_error_response(ex.args[1], 400)), 400

    try:
        logger.info(json.dumps(data, default=str))
        if data["event"] == "user.deactivated":
            if data.get("payload").get("object").get("type"):
                logger.info(
                    "Webhook payload for deactivating the user profile:")

                user_detail = data["payload"]["object"]
                try:
                    user_license_type = user_detail['type']
                except KeyError:
                    msg = f"user license is unknown."
                    logger.error(msg)
                    return json.dumps(build_error_response(msg, 400)), 400
                try:
                    user_id = user_detail['id']
                except KeyError:
                    msg = f"user id is unknown."
                    logger.error(f"user id is unknown.")
                    return json.dumps(build_error_response(msg, 400)), 400

                if user_license_type == USER_PRO_LICENSE_TYPE:
                    logger.debug(
                        "webhook to change pro License to basic License for deactivation"
                    )

                    update_user_license_sync_query = f""" 
                        UPDATE OperationalDataStore.dbo.ZOOM_USER_LOG
                        SET LICENSE_TYPE_CD = 'basic', USER_ENABLED_IND ='F',
                        LAST_UPDATED_DTTM = GETDATE(), LAST_UPDATED_BY_NM = 'Vilt Webhook'
                        WHERE ZOOM_USER_ID = '%s'
                    """

                try:
                    logger.debug('Executing SQL query:')
                    logger.debug(update_user_license_sync_query)
                    cursor.execute(update_user_license_sync_query, (user_id))
                    conn.commit()
                    return "User License Updated Successfully.", 200
                except pyodbc.Error as ex:
                    logging.error(ex.args[1])
                    return json.dumps(build_error_response(ex.args[1],
                                                           400)), 400

            else:
                return "Unhandeled user's details.", 200

        elif data["event"] == "user.activated":
            if data.get("payload").get("object").get("type"):
                logger.info("Webhook payload for activating the user profile:")

                user_detail = data["payload"]["object"]
                try:
                    user_license_type = user_detail['type']
                except KeyError:
                    msg = f"user license is unknown."
                    logger.error(msg)
                    return json.dumps(build_error_response(msg, 400)), 400
                try:
                    user_id = user_detail['id']
                except KeyError:
                    msg = f"user id is unknown."
                    logger.error(msg)
                    return json.dumps(build_error_response(msg, 400)), 400

                if user_license_type == USER_BASIC_LICENSE_TYPE:
                    logger.debug(
                        "webhook to change basic License to pro License for activation"
                    )

                    update_user_license_sync_query = f""" 
                        UPDATE OperationalDataStore.dbo.ZOOM_USER_LOG
                        SET LICENSE_TYPE_CD = 'pro', USER_ENABLED_IND ='T',
                        LAST_UPDATED_DTTM = GETDATE(), LAST_UPDATED_BY_NM = 'Vilt Webhook'
                        WHERE ZOOM_USER_ID = '%s'
                    """
                try:
                    logger.debug('Executing SQL query:')
                    logger.debug(update_user_license_sync_query)
                    cursor.execute(update_user_license_sync_query, (user_id))
                    conn.commit()
                    return "User License Updated Successfully.", 200
                except pyodbc.Error as ex:
                    logging.error(ex.args[1])
                    return json.dumps(build_error_response(ex.args[1],
                                                           400)), 400

            else:
                return "Unhandeled user's details.", 200

    except Exception as error:
        msg = "Invalid data recieved : " + str(error)
        logger.error(msg)
        return json.dumps(build_error_response(msg, 400)), 400


def build_error_response(message, code):
    logger.debug('Entered build_error_response function')
    er = dict()
    er["code"] = code
    er["message"] = message
    logger.debug(f'Return value is "{json.dumps(er, default=str)}"')