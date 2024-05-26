import sqlite3
import re

from typing import Dict, Optional, Callable
from enum import Enum, auto

from utils import CanfigException, TriggerException

DB_FILE = "canfig.sqlite3"

SQLITE3_BUILD_IN_TYPE = ["INTEGER", "REAL", "TEXT", "BLOB"]


class DB:
    @staticmethod
    def __dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def __init__(self, db_dir):
        self.connection = sqlite3.connect(db_dir)
        self.connection.row_factory = self.__dict_factory
        self.cursor = self.connection.cursor()

    def execute(self, sql_command, args=None):
        try:
            if args:
                self.cursor.execute(sql_command, args)
            else:
                self.cursor.execute(sql_command)
        except Exception as e:
            raise CanfigException(e)

    def get_lastrowid(self):
        return self.cursor.lastrowid

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def fetchall(self) -> list:
        return self.cursor.fetchall()

    def close(self):
        self.connection.close()


def CREATE_TABLE_plan(table_name: str, sql: str, FKs: Optional[list] = None):
    ext_cmd = ",\n"

    if FKs:
        for t1, t2 in FKs:
            ext_cmd += f"FOREIGN KEY ({t1}) REFERENCES {t2}({t2}_id),\n"
        ext_cmd = ext_cmd[:-2]

    return f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {table_name}_id  INTEGER PRIMARY KEY ASC,
        {sql}
        {ext_cmd if FKs else ''}
    );
    """


def CREATE_BUILD_IN_plan(build_in_type: str):
    assert (
            build_in_type in SQLITE3_BUILD_IN_TYPE
    ), f"'{build_in_type}' is not build-in type in SQLITE3"
    return f"""
    CREATE TABLE IF NOT EXISTS {build_in_type} (
        {build_in_type}_id INTEGER PRIMARY KEY ASC,
        val {build_in_type}
    );
    """


def CREATE_M2M_plan(tname_1: str, tname_2: str):
    return f"""
    CREATE TABLE IF NOT EXISTS {tname_1}_{tname_2} (
        {tname_1}_id INTEGER,
        {tname_2}_id INTEGER,
        FOREIGN KEY ({tname_1}_id) REFERENCES {tname_1}({tname_1}_id),
        FOREIGN KEY ({tname_2}_id) REFERENCES {tname_2}({tname_2}_id)
    );
    """


def CREATE_CONFIG_INIT_plan(tname: str):
    return f"INSERT INTO {tname} DEFAULT VALUES"


def pre_sql_get_args(pre_sql, patterns: set, neg=False):
    ret = []
    lines = pre_sql.strip().split("\n")
    regex = r"(\w+)\s+(\w+)(\s*\([^)]*\))?\s*"

    for line in lines:
        match = re.search(regex, line.strip())
        if match:
            name, type_name, args = match.groups()
            if args:
                full_type = f"{type_name}{args.strip()}"
            else:
                full_type = type_name

            if (type_name in patterns) != neg:
                ret.append((name, full_type))

    return ret


class Plan:
    __write_plans = []
    __write_taps = []
    __read_plans = []
    __read_taps = []

    __init_flag = False

    __LR_state = "LR_VAL"

    __plan_callback = None
    __build_flag = False

    __write_callbacks: Dict[str, tuple] = {}

    class Operation(Enum):
        EXECUTE = auto()  # execute plan buffer
        UP_LR_STATE = auto()  # update last row state

    def __init__(self):
        pass

    def __plan_closure_maker(self, sql_template: str) -> Callable:
        """

        :param sql_template: sql command with __LR_VAL__ template field
        :return: ready-to-go sql command function closure
        """

        def closure():
            return sql_template.replace("__LR_VAL__", str(self.__LR_state))

        return closure

    def __init_std_plan(self, table_name: str, _config_name: str, value: str | int):
        assert not self.__init_flag, "plan already initialized."
        assert isinstance(value, str) or isinstance(
            value, int
        ), "standard plan value must be a string or int"

        self.__write_plans.append(
            self.__plan_closure_maker(
                f"""
                    UPDATE {table_name} SET 
                    {_config_name} = {"'" + value + "'" if isinstance(value, str) else value}
                    WHERE {table_name}_id = 1;
                """
            )
        )
        self.__write_taps.append(self.Operation.EXECUTE)
        self.__init_flag = True

        # make read plan
        self.__read_plans.append(
            self.__plan_closure_maker(
                f"""
                    SELECT {_config_name} FROM {table_name} WHERE {table_name}_id = 1;
                """
            )
        )

        self.__read_taps.append(self.Operation.EXECUTE)

    def __init_ext_plan(
            self, table_name: str, ext_table_name: str, _config_name: str, values: dict
    ):
        assert not self.__init_flag, "plan already initialized."
        assert isinstance(values, dict), "values must be a dict"

        values_f = [
            f"'{value}'" if isinstance(value, str) else str(value)
            for value in values.values()
        ]

        self.__write_plans.append(
            self.__plan_closure_maker(
                f"""
                    INSERT INTO {ext_table_name} ({",".join(values.keys())})
                    VALUES ({",".join(values_f)});
                """
            )
        )
        self.__write_taps.append(self.Operation.EXECUTE)
        self.__write_taps.append(self.Operation.UP_LR_STATE)

        self.__write_plans.append(
            self.__plan_closure_maker(
                f"""
                    UPDATE {table_name} SET {_config_name} = __LR_VAL__
                    WHERE {table_name}_id = 1
                """
            )
        )
        self.__write_taps.append(self.Operation.EXECUTE)
        self.__init_flag = True

        self.__read_plans.append(
            self.__plan_closure_maker(
                f"""
                    SELECT {",".join(values.keys())} FROM {ext_table_name}
                    WHERE {ext_table_name}_id = (
                        SELECT {_config_name} FROM {table_name} WHERE {table_name}_id = 1
                    )
                """
            )
        )

        self.__read_taps.append(self.Operation.EXECUTE)

    def __init_list_plan(
            self, table_name: str, ext_table_name: str, values: list[Dict]
    ):
        assert not self.__init_flag, "plan already initialized."
        assert isinstance(values, list), "list plan values must be a list"

        self.__write_plans.extend(
            [
                self.__plan_closure_maker(
                    f"""
                        DELETE FROM {table_name};
                """
                ),
                self.__plan_closure_maker(
                    f"""
                        DELETE FROM {ext_table_name}_{table_name};
                    """
                ),
            ]
        )

        self.__write_taps.append(self.Operation.EXECUTE)
        self.__write_taps.append(self.Operation.EXECUTE)

        for config in values:
            values_f = [
                f"'{value}'" if isinstance(value, str) else str(value)
                for value in config.values()
            ]

            self.__write_plans.append(
                self.__plan_closure_maker(
                    f"""
                        INSERT INTO {ext_table_name} ({",".join(config.keys())})
                        VALUES ({",".join(values_f)});
                    """
                )
            )

            self.__write_taps.append(self.Operation.EXECUTE)
            self.__write_taps.append(self.Operation.UP_LR_STATE)

            self.__write_plans.append(
                self.__plan_closure_maker(
                    f"""
                        INSERT INTO {ext_table_name}_{table_name}  ({ext_table_name}_id, {table_name}_id)
                        VALUES (__LR_VAL__, 1)
                    """
                )
            )

            self.__write_taps.append(self.Operation.EXECUTE)

        self.__read_plans.append(
            self.__plan_closure_maker(
                f"""
                    SELECT {",".join(values[0].keys())} FROM {ext_table_name}
                    WHERE {ext_table_name}_id IN (
                        SELECT {ext_table_name}_id FROM {ext_table_name}_{table_name}
                        WHERE {table_name}_id = 1 
                    )
                """
            )
        )

        self.__read_taps.append(self.Operation.EXECUTE)

        self.__init_flag = True

    def init_std_plan(self, table_name: str, _config_name: str):
        def closure(values: str):
            return self.__init_std_plan(table_name, _config_name, values)

        self.__plan_callback = closure

    def init_ext_plan(self, table_name: str, ext_table_name: str, _config_name: str):
        def closure(values: dict):
            return self.__init_ext_plan(
                table_name, ext_table_name, _config_name, values
            )

        self.__plan_callback = closure

    def init_list_plan(self, table_name: str, ext_table_name: str):
        def closure(values: list):
            return self.__init_list_plan(table_name, ext_table_name, values)

        self.__plan_callback = closure

    def bind(self, values):
        self.__write_plans = []
        self.__write_taps = []
        self.__read_plans = []
        self.__read_taps = []
        self.__LR_state = "LR_VAL"

        self.__plan_callback(values)
        self.__build_flag = True

    def execute(self, _db: DB):
        assert self.__build_flag, "bind the plan before execute"
        plan_cursor = 0

        for tap in self.__write_taps:
            if tap == self.Operation.UP_LR_STATE:
                self.__LR_state = _db.get_lastrowid()
            elif tap == self.Operation.EXECUTE:
                _db.execute(self.__write_plans[plan_cursor]())
                _db.commit()
                plan_cursor += 1
            else:
                raise Exception("wrong plan operation")

        self.__LR_state = -1

        # execute trigger callbacks
        for callback_name, (trigger_func_str, env) in self.__write_callbacks.items():
            if isinstance(ret := exec(trigger_func_str, env), TriggerException):
                _db.rollback()
                raise TriggerException(f"Trigger '{callback_name}' failed: {ret.message}")

        print("execute success!")

    def view(self, _db: DB) -> list:
        if not self.__build_flag:
            return []

        plan_cursor = 0

        for tap in self.__read_taps:
            if tap == self.Operation.EXECUTE:
                _db.execute(self.__read_plans[plan_cursor]())
                plan_cursor += 1

        return _db.fetchall()

    def add_trigger(self, trigger_name: str, trigger_func_str: str, env: dict):
        self.__write_callbacks[trigger_name] = (trigger_func_str, env)

    def __str__(self):
        plan_cursor = 0
        ret = "-" * 20
        ret += f"\nWrite Plan (total: {len(self.__write_taps)})\n"
        ret += "-" * 20
        if self.__build_flag:
            for i, tap in enumerate(self.__write_taps):
                ret += f"\nStep {i + 1}: \n"
                if tap == self.Operation.UP_LR_STATE:
                    ret += "\n\t\tUPDATE LR_VAL\n"
                elif tap == self.Operation.EXECUTE:
                    ret += self.__write_plans[plan_cursor]()
                    plan_cursor += 1
                else:
                    raise Exception("wrong plan operation")

            ret += "\n"
        else:
            ret += "\nNOT BUILD YET\n"
        ret += "-" * 20

        plan_cursor = 0
        ret += f"\nRead Plan (total: {len(self.__read_taps)})\n"
        ret += "-" * 20
        if self.__build_flag:
            for i, tap in enumerate(self.__read_taps):
                ret += f"\nStep {i + 1}: \n"
                if tap == self.Operation.EXECUTE:
                    ret += self.__read_plans[plan_cursor]()
                    plan_cursor += 1
                else:
                    raise Exception("wrong plan operation")

            ret += "\n"
        else:
            ret += "\nNOT BUILD YET\n"
        ret += "-" * 20

        return ret


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
                    f"fail to evaluate '{arg}', expect to be {self.__arg_rule[1]}, but is {type(arg).__name__}"
                )

        return self.__pre_sql.replace(self.__arg_rule[0], str(arg)).replace(
            self.__table_name,
            self.format_struct_to_name(self.__table_name + f"({arg})"),
        )

    @staticmethod
    def format_struct_to_name(struct_name):
        # should be consistent to self.__table_name}_{str(arg)
        return re.sub(r"\((\d+)\)", r"_\1", struct_name)


def assign_plan(_final_plan, _plan, _for) -> Plan:
    print(f"assign {_plan['name']}.{_for}")
    if _plan["name"] not in _final_plan:
        _final_plan[_plan["name"]] = {}

    assert _for not in _final_plan[_plan["name"]], f"{_for} already init"
    _final_plan[_plan["name"]][_for] = Plan()
    return _final_plan[_plan["name"]][_for]
