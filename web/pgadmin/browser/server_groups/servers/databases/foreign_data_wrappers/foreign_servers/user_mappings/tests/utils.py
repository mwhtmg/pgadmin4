##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2022, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


import os
import sys
import traceback
import json

from regression.python_test_utils.test_utils import get_db_connection

CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))
with open(f"{CURRENT_PATH}/user_mapping_test_data.json") as data_file:
    test_cases = json.load(data_file)


def get_um_data(db_user, server):

    return {
        "name": db_user,
        "um_options": [],
        "umoptions": [
            {"umoption": "user", "umvalue": server["username"]},
            {"umoption": "password", "umvalue": server["db_password"]},
        ],
    }


def create_user_mapping(server, db_name, fsrv_name):
    """
    This function will create user mapping under the existing
    dummy database.
    :param server: server details
    :type server: dict
    :param db_name: database name
    :type db_name: str
    :param fsrv_name: FS name
    :type fsrv_name: str
    :return um_id: user mapping id
    :rtype: int
    """
    try:
        connection = get_db_connection(db_name,
                                       server['username'],
                                       server['db_password'],
                                       server['host'],
                                       server['port'],
                                       server['sslmode'])
        old_isolation_level = connection.isolation_level
        connection.set_isolation_level(0)
        pg_cursor = connection.cursor()
        query = f"CREATE USER MAPPING FOR {server['username']} SERVER {fsrv_name} OPTIONS (user '{server['username']}', password '{server['db_password']}')"
        pg_cursor.execute(query)
        connection.set_isolation_level(old_isolation_level)
        connection.commit()
        # Get 'oid' from newly created user mapping
        pg_cursor.execute(
            f"select umid from pg_catalog.pg_user_mappings where srvname = '{fsrv_name}' order by umid asc limit 1"
        )
        um_id = oid[0] if (oid := pg_cursor.fetchone()) else ''
        connection.close()
        return um_id
    except Exception:
        traceback.print_exc(file=sys.stderr)


def verify_user_mapping(server, db_name, fsrv_name):
    """
    This function will verify current foreign server.
    :param server: server details
    :type server: dict
    :param db_name: database name
    :type db_name: str
    :param fsrv_name: FS name
    :type fsrv_name: str
    :return user_mapping: user mapping record
    :rtype: tuple
    """
    try:
        connection = get_db_connection(db_name,
                                       server['username'],
                                       server['db_password'],
                                       server['host'],
                                       server['port'],
                                       server['sslmode'])
        pg_cursor = connection.cursor()
        pg_cursor.execute(
            "select umid from pg_catalog.pg_user_mappings "
            "where srvname = '%s' order by umid asc limit 1" % fsrv_name)
        user_mapping = pg_cursor.fetchone()
        connection.close()
        return user_mapping
    except Exception:
        traceback.print_exc(file=sys.stderr)
