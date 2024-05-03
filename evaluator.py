import sqlite3
import pickle
import sys
import re

from typing import Callable, Optional

from utils import *

DB_FILE = 'canfig.sqlite3'


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


def CREATE_TABLE_plan(table_name: str, sql: str):
    return f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        {table_name}_id  INTEGER PRIMARY KEY ASC,
        {sql}
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

    def make(self, arg):
        if arg is None:
            return self.__pre_sql.replace(self.__arg_rule[0], self.__arg_rule[2])

        if self.__arg_rule[1] != type(arg).__name__:
            raise Exception(f"fail to evaluate '{arg}', expect to be {type(arg).__name__}, but is {self.__arg_rule[1]}")

        return self.__pre_sql.replace(self.__arg_rule[0], str(arg))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        exit(1)

    with open(cplan_file := sys.argv[1], 'rb') as f:
        cplan_data = pickle.load(f)

    db = DB(DB_FILE)
    print("load db instance.")

    pre_plan_keywords = ['LIST']

    for plan in cplan_data['sql_query']:
        if plan['type'] == 'STRUCT':
            if not plan['pre']:
                db.execute(CREATE_TABLE_plan(table_name=plan['name'],
                                             sql=plan['sql']))
                print(f"evaluate struct: {plan['name']}")

            elif 'arg' in plan:
                plan_rule = re.match(r'(\w+):(\w+)\s*=\s*(\d+)', plan['arg']).groups()
                pre_plan = PreSQL(table_name=f"{plan['name']}", pre_sql=plan['sql'], arg_rule=plan_rule)
                plan['pre_plan'] = pre_plan
                db.execute(pre_plan.make(None))
                pre_plan_keywords.append(plan['name'])
                print(f"evaluate struct: {plan['name']}")

        elif plan['type'] == 'CONFIG':
            # pre_sql_replace(pre_sql=plan['sql'],
            #                 patterns=pre_plan_keywords,
            #                 post_arg_func=lambda _: "a")
            print(pre_sql_get_args(plan['sql'], pre_plan_keywords))
            print(plan['sql'])
