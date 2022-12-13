##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2022, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Schema collection node helper class"""

import json
import copy
import re

from flask import render_template

from pgadmin.browser.collection import CollectionNodeModule
from pgadmin.utils.ajax import internal_server_error
from pgadmin.utils.driver import get_driver
from config import PG_DEFAULT_DRIVER
from pgadmin.utils.constants import DATATYPE_TIME_WITH_TIMEZONE,\
    DATATYPE_TIME_WITHOUT_TIMEZONE,\
    DATATYPE_TIMESTAMP_WITH_TIMEZONE,\
    DATATYPE_TIMESTAMP_WITHOUT_TIMEZONE


class SchemaChildModule(CollectionNodeModule):
    """
    Base class for the schema child node.

    Some of the node may be/may not be allowed in certain catalog nodes.
    i.e.
    Do not show the schema objects under pg_catalog, pgAgent, etc.

    Looks at two parameters CATALOG_DB_SUPPORTED, SUPPORTED_SCHEMAS.

    Schema child objects like catalog_objects are only supported for
    'pg_catalog', and objects like 'jobs' & 'schedules' are only supported for
    the 'pgagent' schema.

    For catalog_objects, we should set:
        CATALOG_DB_SUPPORTED = False
        SUPPORTED_SCHEMAS = ['pg_catalog']

    For jobs & schedules, we should set:
        CATALOG_DB_SUPPORTED = False
        SUPPORTED_SCHEMAS = ['pgagent']
    """
    CATALOG_DB_SUPPORTED = True
    SUPPORTED_SCHEMAS = None

    def backend_supported(self, manager, **kwargs):
        return (
            (
                (
                    kwargs['is_catalog'] and
                    (
                        (
                            self.CATALOG_DB_SUPPORTED and
                            kwargs['db_support']
                        ) or (
                            not self.CATALOG_DB_SUPPORTED and
                            not kwargs[
                                'db_support'] and
                            (
                                self.SUPPORTED_SCHEMAS is None or
                                kwargs[
                                    'schema_name'] in self.SUPPORTED_SCHEMAS
                            )
                        )
                    )
                ) or
                (
                    not kwargs['is_catalog'] and self.CATALOG_DB_SUPPORTED
                )
            ) and
            CollectionNodeModule.backend_supported(self, manager, **kwargs)
        )

    @property
    def module_use_template_javascript(self):
        """
        Returns whether Jinja2 template is used for generating the javascript
        module.
        """
        return False


class DataTypeReader:
    """
    DataTypeReader Class.

    This class includes common utilities for data-types.

    Methods:
    -------
    * get_types(conn, condition):
      - Returns data-types on the basis of the condition provided.
    """

    def _get_types_sql(self, conn, condition, add_serials, schema_oid):
        """
        Get sql for types.
        :param conn: connection
        :param condition: Condition for sql
        :param add_serials: add_serials flag
        :param schema_oid: schema iod.
        :return: sql for get type sql result, status and response.
        """
        # Check if template path is already set or not
        # if not then we will set the template path here
        manager = self.manager if hasattr(self, 'manager') else conn.manager
        if not hasattr(self, 'data_type_template_path'):
            self.data_type_template_path = 'datatype/sql/' + (
                '#{0}#'.format(manager.version)
            )
        sql = render_template(
            "/".join([self.data_type_template_path, 'get_types.sql']),
            condition=condition,
            add_serials=add_serials,
            schema_oid=schema_oid
        )
        status, rset = conn.execute_2darray(sql)

        return status, rset

    @staticmethod
    def _types_length_checks(length, typeval, precision):
        min_val = 0
        max_val = 0
        if length:
            min_val = 0 if typeval == 'D' else 1
            if precision:
                max_val = 1000
            elif min_val:
                # Max of integer value
                max_val = 2147483647
            else:
                # Max value is 6 for data type like
                # interval, timestamptz, etc..
                max_val = 6 if typeval == 'D' else 10
        return min_val, max_val

    def get_types(self, conn, condition, add_serials=False, schema_oid=''):
        """
        Returns data-types including calculation for Length and Precision.

        Args:
            conn: Connection Object
            condition: condition to restrict SQL statement
            add_serials: If you want to serials type
            schema_oid: If needed pass the schema OID to restrict the search
        """
        res = []
        try:
            status, rset = self._get_types_sql(conn, condition, add_serials,
                                               schema_oid)
            if not status:
                return status, rset

            for row in rset['rows']:
                # Attach properties for precision
                # & length validation for current type
                precision = False
                length = False

                # Check if the type will have length and precision or not
                if row['elemoid']:
                    length, precision, typeval = self.get_length_precision(
                        row['elemoid'])

                min_val, max_val = DataTypeReader._types_length_checks(
                    length, typeval, precision)

                res.append({
                    'label': row['typname'], 'value': row['typname'],
                    'typval': typeval, 'precision': precision,
                    'length': length, 'min_val': min_val, 'max_val': max_val,
                    'is_collatable': row['is_collatable'],
                    'oid': row['oid']
                })

        except Exception as e:
            return False, str(e)

        return True, res

    @staticmethod
    def get_length_precision(elemoid_or_name):
        typeval = ''

        # Check against PGOID/typename for specific type
        if elemoid_or_name:
            if elemoid_or_name in (1560, 'bit',
                                   1561, 'bit[]',
                                   1562, 'varbit', 'bit varying',
                                   1563, 'varbit[]', 'bit varying[]',
                                   1042, 'bpchar', 'character',
                                   1043, 'varchar', 'character varying',
                                   1014, 'bpchar[]', 'character[]',
                                   1015, 'varchar[]', 'character varying[]'):
                typeval = 'L'
            elif elemoid_or_name in (1083, 'time',
                                     DATATYPE_TIME_WITHOUT_TIMEZONE,
                                     1114, 'timestamp',
                                     DATATYPE_TIMESTAMP_WITHOUT_TIMEZONE,
                                     1115, 'timestamp[]',
                                     'timestamp without time zone[]',
                                     1183, 'time[]',
                                     'time without time zone[]',
                                     1184, 'timestamptz',
                                     DATATYPE_TIMESTAMP_WITH_TIMEZONE,
                                     1185, 'timestamptz[]',
                                     'timestamp with time zone[]',
                                     1186, 'interval',
                                     1187, 'interval[]', 'interval[]',
                                     1266, 'timetz',
                                     DATATYPE_TIME_WITH_TIMEZONE,
                                     1270, 'timetz', 'time with time zone[]'):
                typeval = 'D'
            elif elemoid_or_name in (1231, 'numeric[]',
                                     1700, 'numeric'):
                typeval = 'P'
            else:
                typeval = ' '

        precision = typeval == 'P'
        length = precision or typeval in {'L', 'D'}
        return length, precision, typeval

    @staticmethod
    def _check_typmod(typmod, name):
        """
        Check type mode ad return length as per type.
        :param typmod:type mode.
        :param name: name of type.
        :return:
        """
        length = '('
        if name == 'numeric':
            _len = (typmod - 4) >> 16
            _prec = (typmod - 4) & 0xffff
            length += str(_len)
            if _prec is not None:
                length += f',{str(_prec)}'
        elif name in [
            'time',
            'timetz',
            DATATYPE_TIME_WITHOUT_TIMEZONE,
            DATATYPE_TIME_WITH_TIMEZONE,
            'timestamp',
            'timestamptz',
            DATATYPE_TIMESTAMP_WITHOUT_TIMEZONE,
            DATATYPE_TIMESTAMP_WITH_TIMEZONE,
            'bit',
            'bit varying',
            'varbit',
        ]:
            _prec = 0
            _len = typmod
            length += str(_len)
        elif name == 'interval':
            _prec = 0
            _len = typmod & 0xffff
            # Max length for interval data type is 6
            # If length is greater then 6 then set length to None
            if _len > 6:
                _len = ''
            length += str(_len)
        elif name == 'date':
            # Clear length
            length = ''
        else:
            _len = typmod - 4
            _prec = 0
            length += str(_len)

        if length != "":
            length += ')'

        return length

    @staticmethod
    def _get_full_type_value(name, schema, length, array):
        """
        Generate full type value as per req.
        :param name: type name.
        :param schema: schema name.
        :param length: length.
        :param array: array of types
        :return: full type value
        """
        if name == 'char' and schema == 'pg_catalog':
            return f'"char"{array}'
        elif name == DATATYPE_TIME_WITH_TIMEZONE:
            return f'time{length} with time zone{array}'
        elif name == DATATYPE_TIME_WITHOUT_TIMEZONE:
            return f'time{length} without time zone{array}'
        elif name == DATATYPE_TIMESTAMP_WITH_TIMEZONE:
            return f'timestamp{length} with time zone{array}'
        elif name == DATATYPE_TIMESTAMP_WITHOUT_TIMEZONE:
            return f'timestamp{length} without time zone{array}'
        else:
            return name + length + array

    @staticmethod
    def _check_schema_in_name(typname, schema):
        """
        Above 7.4, format_type also sends the schema name if it's not
        included in the search_path, so we need to skip it in the typname
        :param typename: typename for check.
        :param schema: schema name for check.
        :return: name
        """
        if typname.find(f'{schema}".') >= 0:
            return typname[len(schema) + 3]
        elif typname.find(f'{schema}.') >= 0:
            return typname[len(schema) + 1]
        else:
            return typname

    @staticmethod
    def get_full_type(nsp, typname, is_dup, numdims, typmod):
        """
        Returns full type name with Length and Precision.

        Args:
            conn: Connection Object
            condition: condition to restrict SQL statement
        """
        schema = nsp if nsp is not None else ''
        name = ''
        array = ''
        name = DataTypeReader._check_schema_in_name(typname, schema)

        if name.startswith('_'):
            if not numdims:
                numdims = 1
            name = name[1:]

        if name.endswith('[]'):
            if not numdims:
                numdims = 1
            name = name[:-2]

        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]

        if numdims > 0:
            while numdims:
                array += '[]'
                numdims -= 1

        length = DataTypeReader._check_typmod(typmod, name) if typmod != -1 else ''
        return DataTypeReader._get_full_type_value(name, schema, length, array)

    @classmethod
    def parse_type_name(cls, type_name):
        """
        Returns prase type name without length and precision
        so that we can match the end result with types in the select2.

        Args:
            self: self
            type_name: Type name
        """

        # Manual Data type formatting
        # If data type has () with them then we need to remove them
        # eg bit(1) because we need to match the name with combobox

        is_array = False
        if type_name.endswith('[]'):
            is_array = True
            type_name = type_name.rstrip('[]')

        idx = type_name.find('(')
        if idx and type_name.endswith(')'):
            type_name = type_name[:idx]
        # We need special handling of timestamp types as
        # variable precision is between the type
        elif idx and type_name.startswith("time"):
            end_idx = type_name.find(')')
            # If we found the end then form the type string
            if end_idx != 1:
                from re import sub as sub_str
                pattern = r'(\(\d+\))'
                type_name = sub_str(pattern, '', type_name)
        # We need special handling for interval types like
        # interval hours to minute.
        elif type_name.startswith("interval"):
            type_name = 'interval'

        if is_array:
            type_name += "[]"

        return type_name

    @classmethod
    def parse_length_precision(cls, fulltype, is_tlength, is_precision):
        """
        Parse the type string and split length, precision.
        :param fulltype: type string
        :param is_tlength: is length type
        :param is_precision: is precision type
        :return: length, precision
        """
        t_len, t_prec = None, None
        if is_tlength:
            if is_precision:
                if match_obj := re.search(r'(\d+),(\d+)', fulltype):
                    t_len = match_obj[1]
                    t_prec = match_obj[2]
            elif match_obj := re.search(r'(\d+)', fulltype):
                t_len = match_obj[1]
                t_prec = None

        return t_len, t_prec


def trigger_definition(data):
    """
    This function will set the trigger definition details from the raw data

    Args:
        data: Properties data

    Returns:
        Updated properties data with trigger definition
    """

    # Here we are storing trigger definition
    # We will use it to check trigger type definition
    trigger_definition = {
        'TRIGGER_TYPE_ROW': (1 << 0),
        'TRIGGER_TYPE_BEFORE': (1 << 1),
        'TRIGGER_TYPE_INSERT': (1 << 2),
        'TRIGGER_TYPE_DELETE': (1 << 3),
        'TRIGGER_TYPE_UPDATE': (1 << 4),
        'TRIGGER_TYPE_TRUNCATE': (1 << 5),
        'TRIGGER_TYPE_INSTEAD': (1 << 6)
    }

    # Fires event definition
    if data['tgtype'] & trigger_definition['TRIGGER_TYPE_BEFORE']:
        data['fires'] = 'BEFORE'
    elif data['tgtype'] & trigger_definition['TRIGGER_TYPE_INSTEAD']:
        data['fires'] = 'INSTEAD OF'
    else:
        data['fires'] = 'AFTER'

    # Trigger of type definition
    data['is_row_trigger'] = bool(
        data['tgtype'] & trigger_definition['TRIGGER_TYPE_ROW']
    )
    # Event definition
    data['evnt_insert'] = bool(
        data['tgtype'] & trigger_definition['TRIGGER_TYPE_INSERT']
    )
    data['evnt_delete'] = bool(
        data['tgtype'] & trigger_definition['TRIGGER_TYPE_DELETE']
    )
    data['evnt_update'] = bool(
        data['tgtype'] & trigger_definition['TRIGGER_TYPE_UPDATE']
    )
    data['evnt_truncate'] = bool(
        data['tgtype'] & trigger_definition['TRIGGER_TYPE_TRUNCATE']
    )
    return data


def parse_rule_definition(res):
    """
    This function extracts:
    - events
    - do_instead
    - statements
    - condition
    from the defintion row, forms an array with fields and returns it.
    """
    res_data = []
    try:
        res_data = res['rows'][0]
        data_def = res_data['definition']
        import re

        # Parse data for condition
        condition = ''
        condition_part_match = re.search(
            r"((?:ON)\s+(?:[\s\S]+?)"
            r"(?:TO)\s+(?:[\s\S]+?)(?:DO))", data_def)
        if condition_part_match is not None:
            condition_part = condition_part_match[1]

            condition_match = re.search(
                r"(?:WHERE)\s+(\([\s\S]*\))\s+(?:DO)", condition_part)

            if condition_match is not None:
                condition = condition_match[1]
                # also remove enclosing brackets
                if condition.startswith('(') and condition.endswith(')'):
                    condition = condition[1:-1]

                    # Parse data for statements
        statement_match = re.search(
            r"(?:DO\s+)(?:INSTEAD\s+)?([\s\S]*)(?:;)", data_def)

        statement = ''
        if statement_match is not None:
            statement = statement_match[1]
            # also remove enclosing brackets
            if statement.startswith('(') and statement.endswith(')'):
                statement = statement[1:-1]

        # set columns parse data
        res_data['event'] = {
            '1': 'SELECT',
            '2': 'UPDATE',
            '3': 'INSERT',
            '4': 'DELETE'
        }[res_data['ev_type']]
        res_data['do_instead'] = res_data['is_instead']
        res_data['statements'] = statement
        res_data['condition'] = condition
    except Exception as e:
        return internal_server_error(errormsg=str(e))
    return res_data


class VacuumSettings:
    """
    VacuumSettings Class.

    This class includes common utilities to fetch and parse
    vacuum defaults settings.

    Methods:
    -------
    * get_vacuum_table_settings(conn):
      - Returns vacuum table defaults settings.

    * get_vacuum_toast_settings(conn):
      - Returns vacuum toast defaults settings.

    * parse_vacuum_data(conn, result, type):
      - Returns result of an associated array
        of fields name, label, value and column_type.
        It adds name, label, column_type properties of table/toast
        vacuum into the array and returns it.
        args:
        * conn - It is db connection object
        * result - Resultset of vacuum data
        * type - table/toast vacuum type

    """
    vacuum_settings = dict()

    def fetch_default_vacuum_settings(self, conn, sid, setting_type):
        """
        This function is used to fetch and cached the default vacuum settings
        for specified server id.
        :param conn: Connection Object
        :param sid:  Server ID
        :param setting_type: Type (table or toast)
        :return:
        """
        if sid in VacuumSettings.vacuum_settings:
            if setting_type in VacuumSettings.vacuum_settings[sid]:
                return VacuumSettings.vacuum_settings[sid][setting_type]
        else:
            VacuumSettings.vacuum_settings[sid] = {}

        # returns an array of name & label values
        vacuum_fields = render_template("vacuum_settings/vacuum_fields.json")
        vacuum_fields = json.loads(vacuum_fields)

        # returns an array of setting & name values
        vacuum_fields_keys = "'" + "','".join(
            vacuum_fields[setting_type].keys()) + "'"
        SQL = render_template('vacuum_settings/sql/vacuum_defaults.sql',
                              columns=vacuum_fields_keys)

        status, res = conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=res)

        for row in res['rows']:
            row_name = row['name']
            row['name'] = vacuum_fields[setting_type][row_name][0]
            row['label'] = vacuum_fields[setting_type][row_name][1]
            row['column_type'] = vacuum_fields[setting_type][row_name][2]

        VacuumSettings.vacuum_settings[sid][setting_type] = res['rows']
        return VacuumSettings.vacuum_settings[sid][setting_type]

    def get_vacuum_table_settings(self, conn, sid):
        """
        Fetch the default values for autovacuum
        fields, return an array of
          - label
          - name
          - setting
        values
        """
        return self.fetch_default_vacuum_settings(conn, sid, 'table')

    def get_vacuum_toast_settings(self, conn, sid):
        """
        Fetch the default values for autovacuum
        fields, return an array of
          - label
          - name
          - setting
        values
        """
        return self.fetch_default_vacuum_settings(conn, sid, 'toast')

    def parse_vacuum_data(self, conn, result, type):
        """
        This function returns result of an associated array
        of fields name, label, value and column_type.
        It adds name, label, column_type properties of table/toast
        vacuum into the array and returns it.
        args:
        * conn - It is db connection object
        * result - Resultset of vacuum data
        * type - table/toast vacuum type
        """

        vacuum_settings_tmp = copy.deepcopy(self.fetch_default_vacuum_settings(
            conn, self.manager.sid, type))

        for row in vacuum_settings_tmp:
            row_name = row['name']
            if type == 'toast':
                row_name = 'toast_{0}'.format(row['name'])
            if result.get(row_name, None) is not None:
                value = float(result[row_name])
                row['value'] = int(value) if value % 1 == 0 else value
            else:
                row.pop('value', None)

        return vacuum_settings_tmp


def get_schema(sid, did, scid):
    """
    This function will return the schema name.
    """

    driver = get_driver(PG_DEFAULT_DRIVER)
    manager = driver.connection_manager(sid)
    conn = manager.connection(did=did)

    ver = manager.version
    server_type = manager.server_type

    # Fetch schema name
    status, schema_name = conn.execute_scalar(
        render_template("/".join(['schemas',
                                  '{0}/#{1}#'.format(server_type,
                                                     ver),
                                  'sql/get_name.sql']),
                        conn=conn, scid=scid
                        )
    )

    return status, schema_name


def get_schemas(conn, show_system_objects=False):
    """
    This function will return the schemas.
    """

    ver = conn.manager.version
    server_type = conn.manager.server_type

    SQL = render_template(
        "/".join(['schemas',
                  '{0}/#{1}#'.format(server_type, ver),
                  'sql/nodes.sql']),
        show_sysobj=show_system_objects,
        schema_restrictions=None
    )

    status, rset = conn.execute_2darray(SQL)
    return status, rset
