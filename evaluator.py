import sqlite3
import pickle
import sys
import re

from typing import Callable, Optional

from utils import *

DB_FILE = 'canfig.sqlite3'

SQLITE3_BUILD_IN_TYPE = ["INTEGER", "REAL", "TEXT", "BLOB"]


class DB:
    def __init__(self, db_dir):
        self.connection = sqlite3.connect(db_dir)
        self.cursor = self.connection.cursor()

    def execute(self, sql_command, args=None):
        if args:
            self.cursor.execute(sql_command, args)
        else:
            self.cursor.execute(sql_command)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def CREATE_TABLE_plan(table_name: str, sql: str, FKs: Optional[list] = None):
    ext_cmd = ",\n"

    if FKs:
        for t1, t2 in FKs:
            ext_cmd += f"FOREIGN KEY ({t1}_id) REFERENCES {t2}({t2}_id),\n"
        ext_cmd = ext_cmd[:-2]

    return f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        {table_name}_id  INTEGER PRIMARY KEY ASC,
        {sql}
        {ext_cmd if FKs else ''}
    );
    '''


def CREATE_BUILD_IN_plan(build_in_type: str):
    assert build_in_type in SQLITE3_BUILD_IN_TYPE, f"'{build_in_type}' is not build-in type in SQLITE3"
    return f'''
    CREATE TABLE IF NOT EXISTS {build_in_type} (
        {build_in_type}_id INTEGER PRIMARY KEY ASC,
        val {build_in_type}
    );
    '''


def CREATE_M2M_plan(tname_1: str, tname_2: str):
    return f'''
    CREATE TABLE IF NOT EXISTS {tname_1}_{tname_2} (
        {tname_1}_id INTEGER,
        {tname_2}_id INTEGER,
        FOREIGN KEY ({tname_1}_id) REFERENCES {tname_1}({tname_1}_id),
        FOREIGN KEY ({tname_2}_id) REFERENCES {tname_2}({tname_2}_id)
    );
    '''


def pre_sql_get_args(pre_sql, patterns: list):
    ret = []
    for pattern in patterns:
        regex = rf"{pattern}\(.*?\)|{pattern}"

        ret += re.findall(regex, pre_sql)
    return ret


def pre_sql_replace(pre_sql, patterns: list, post_arg_func: Callable):
    for pattern in patterns:
        regex = rf"{pattern}\(.*?\)|{pattern}"

        def replacement(match):
            if '(' in match.group(0):
                return post_arg_func(match.group(0).split('(')[1].strip(')'))
            else:
                return post_arg_func()

        pre_sql = re.sub(regex, replacement, pre_sql)
    return pre_sql


class PreSQL:
    def __init__(self, table_name: str, pre_sql: str, arg_rule: tuple):
        self.__pre_sql = CREATE_TABLE_plan(table_name, pre_sql)
        self.__arg_rule = arg_rule
        self.__table_name = table_name

    def make(self, arg):
        if arg is None:
            return self.__pre_sql.replace(self.__arg_rule[0], self.__arg_rule[2])

        if self.__arg_rule[1] != type(arg).__name__:
            try:
                arg = type(self.__arg_rule[1])(arg)
            except TypeError:
                raise Exception(
                    f"fail to evaluate '{arg}', expect to be {self.__arg_rule[1]}, but is {type(arg).__name__}")

        return self.__pre_sql \
            .replace(self.__arg_rule[0], str(arg)) \
            .replace(self.__table_name, f"{self.__table_name}_{str(arg)}")

    @staticmethod
    def format_struct_to_name(struct_name):
        # should be consistent to self.__table_name}_{str(arg)
        return re.sub(r'\((\d+)\)', r'_\1', struct_name)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        exit(1)

    assert sys.argv[1].endswith('.candy'), "input file must be .candy"

    with open(cplan_file := sys.argv[1], 'rb') as f:
        cplan_data = pickle.load(f)

    db = DB(DB_FILE)
    print("load db instance.")

    # structs that already been created
    struct_list = []

    # evaluate STRUCT
    for plan in cplan_data['sql_query']:
        if plan['type'] == 'STRUCT':
            if not plan['pre']:
                db.execute(CREATE_TABLE_plan(table_name=plan['name'],
                                             sql=plan['sql']))
                struct_list.append(plan['name'])
                print(f"evaluate struct: {plan['name']}")

            elif 'arg' in plan:
                plan_rule = re.match(r'(\w+):(\w+)\s*=\s*(\d+)', plan['arg']).groups()
                pre_plan = PreSQL(table_name=f"{plan['name']}", pre_sql=plan['sql'], arg_rule=plan_rule)
                plan['pre_plan'] = pre_plan
                db.execute(pre_plan.make(None))
                struct_list.append(plan['name'])
                print(f"evaluate struct: {plan['name']}")

    # evaluate CONFIG
    for plan in cplan_data['sql_query']:
        if plan['type'] == 'CONFIG':
            # print(plan['sql'])
            m2m_plans = []

            if ret := re.findall(r'LIST\(([^()]*(?:\([^)]*\))?[^()]*)\)', plan['sql']):
                # Evaluate LIST, basically create many-to-many relation with the
                # list argument.
                for req_struct in ret:
                    if req_struct not in struct_list:
                        # create missing struct
                        if not bool(re.fullmatch(r'\w+\([^()]*\)', req_struct)):
                            # case 1: not pre-sql type, that is build-in-type
                            assert req_struct in SQLITE3_BUILD_IN_TYPE, f"invalid type LIST{req_struct}"
                            db.execute(CREATE_BUILD_IN_plan(req_struct))
                            print(f"evaluate build-in struct: {req_struct}")
                        else:
                            # case 2: pre-sql type, need create PreSQL instance
                            pre_sql_struct = re.search(r'(\w+)\(', req_struct).groups()[0]
                            assert pre_sql_struct in struct_list, f'Fail to build LIST({req_struct}) ' \
                                                                  f'due to struct {req_struct} not exist'
                            # db.execute(cplan_data['sql_query'])
                            for i in cplan_data['sql_query']:
                                if i['name'] == pre_sql_struct:
                                    db.execute(i['pre_plan'].make(re.search(r'\((.*?)\)', req_struct).groups()[0]))
                                    break
                            print(f"evaluate {req_struct}")

                    # should be consistent to how PreSQL format the pre-sql struct
                    post_struct = PreSQL.format_struct_to_name(req_struct)
                    m2m_plans.append(CREATE_M2M_plan(tname_1=post_struct,
                                                     tname_2=plan['name']))
                    struct_list.append(post_struct)

                # replace LIST to be NULL type
                plan['sql'] = re.sub(r'LIST\(([^()]*(?:\([^()]*\)[^()]*)*)\)', 'NULL', plan['sql'])

            # Evaluate struct referencing
            struct_ref_fks = []
            struct_ref = pre_sql_get_args(plan['sql'], struct_list)
            for ref in struct_ref:
                struct_ref_fks.append((plan['name'], PreSQL.format_struct_to_name(ref)))

            # create db
            db_query = CREATE_TABLE_plan(table_name=plan['name'],
                                         sql=plan['sql'],
                                         FKs=struct_ref_fks)

            print(db_query)

            db.execute(db_query)

            # create m2m relation
            for p in m2m_plans:
                db.execute(p)

            print(f"evaluate config: {plan['name']}")
