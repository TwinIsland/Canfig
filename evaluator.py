import sqlite3
import pickle
import subprocess
import sys
import re

from typing import Dict, Optional, Callable
from enum import Enum, auto

from utils import CanfigException

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
        assert not self.__build_flag, "plan already built"
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

    def view(self, _db: DB) -> list:
        assert self.__build_flag, "build the plan before execute"
        plan_cursor = 0

        for tap in self.__read_taps:
            if tap == self.Operation.EXECUTE:
                _db.execute(self.__read_plans[plan_cursor]())
                plan_cursor += 1

        return _db.fetchall()

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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        exit(1)

    assert sys.argv[1].endswith(".candy"), "input file must be .candy"

    with open(cplan_file := sys.argv[1], "rb") as f:
        cplan_data = pickle.load(f)

    subprocess.run(["rm", DB_FILE])

    db = DB(DB_FILE)
    print("load db instance.")

    # structs that already been created
    struct_set: set = set()

    # struct that hold IO plan for each config
    final_plan: Dict[str, Dict[str, Plan]] = dict()

    # evaluate STRUCT
    for plan in cplan_data["sql_query"]:
        if plan["type"] == "STRUCT":
            if not plan["pre"]:
                db.execute(CREATE_TABLE_plan(table_name=plan["name"], sql=plan["sql"]))
                struct_set.add(plan["name"])
                print(f"evaluate struct: {plan['name']}")

            elif "arg" in plan:
                plan_rule = re.match(r"(\w+):(\w+)\s*=\s*(\d+)", plan["arg"]).groups()
                pre_plan = PreSQL(
                    table_name=f"{plan['name']}",
                    pre_sql=plan["sql"],
                    arg_rule=plan_rule,
                )
                plan["pre_plan"] = pre_plan
                db.execute(pre_plan.make(None))
                struct_set.add(plan["name"])
                print(f"evaluate struct: {plan['name']}")

    # evaluate CONFIG
    for plan in cplan_data["sql_query"]:
        if plan["type"] == "CONFIG":
            # print(plan['sql'])
            print(f"\nevaluate config: {plan['name']}")

            m2m_plans = []
            m2m_tables = []

            if list_matches := re.findall(
                r"(\w+)\s+LIST\(([^()]*(?:\([^)]*\))?[^()]*)\)", plan["sql"]
            ):
                # Evaluate LIST, basically create many-to-many relation with the
                # list argument.
                for field_pair in list_matches:
                    config_name, req_struct = field_pair
                    if req_struct not in struct_set:
                        # create missing struct
                        if not bool(re.fullmatch(r"\w+\([^()]*\)", req_struct)):
                            # case 1: not pre-sql type, that is build-in-type
                            assert (
                                req_struct in SQLITE3_BUILD_IN_TYPE
                            ), f"invalid type LIST{req_struct}"
                            db.execute(CREATE_BUILD_IN_plan(req_struct))
                            print(f"evaluate build-in struct: {req_struct}")
                        else:
                            # case 2: pre-sql type, need create PreSQL instance
                            pre_sql_struct = re.search(r"(\w+)\(", req_struct).groups()[
                                0
                            ]
                            assert pre_sql_struct in struct_set, (
                                f"Fail to build LIST({req_struct}) "
                                f"due to struct {req_struct} not exist"
                            )
                            # db.execute(cplan_data['sql_query'])
                            for i in cplan_data["sql_query"]:
                                if i["name"] == pre_sql_struct:
                                    db.execute(
                                        i["pre_plan"].make(
                                            re.search(
                                                r"\((.*?)\)", req_struct
                                            ).groups()[0]
                                        )
                                    )
                                    break
                            print(f"evaluate {req_struct}")

                    post_struct = PreSQL.format_struct_to_name(req_struct)
                    m2m_plans.append(
                        CREATE_M2M_plan(tname_1=post_struct, tname_2=plan["name"])
                    )

                    plan_ptr = assign_plan(
                        _final_plan=final_plan, _plan=plan, _for=config_name
                    )

                    plan_ptr.init_list_plan(
                        table_name=plan["name"],
                        ext_table_name=post_struct,
                    )

                    # should be consistent on how CREATE_M2M_plan create m2m table name
                    m2m_tables.append(f"{post_struct}_{plan['name']}")
                    struct_set.add(post_struct)

                # replace LIST to be NULL type
                plan["sql"] = re.sub(
                    r"LIST\(([^()]*(?:\([^()]*\)[^()]*)*)\)", "NULL", plan["sql"]
                )

            # Evaluate struct referencing
            struct_ref_fks = []
            struct_ref = pre_sql_get_args(plan["sql"], struct_set)
            for ref in struct_ref:
                plan_ptr = assign_plan(final_plan, plan, ref[0])
                plan_ptr.init_ext_plan(
                    table_name=plan["name"],
                    ext_table_name=PreSQL.format_struct_to_name(ref[1]),
                    _config_name=ref[0],
                )

                struct_ref_fks.append((ref[0], PreSQL.format_struct_to_name(ref[1])))

            # print(plan['sql'])
            # print(pre_sql_get_args(plan['sql'], struct_set))
            # print(pre_sql_get_args(plan['sql'], struct_set, True))

            for ref in pre_sql_get_args(plan["sql"], struct_set, True):
                if ref[1] != "NULL":
                    plan_ptr = assign_plan(final_plan, plan, ref[0])
                    plan_ptr.init_std_plan(table_name=plan["name"], _config_name=ref[0])

            # create db
            db_query = CREATE_TABLE_plan(
                table_name=plan["name"], sql=plan["sql"], FKs=struct_ref_fks
            )
            db.execute(db_query)

            # create m2m relation
            for p in m2m_plans:
                db.execute(p)

            # init config tables
            db.execute(CREATE_CONFIG_INIT_plan(plan["name"]))

            db.commit()

            print(f"finish evaluate config: {plan['name']}")

    # TEST CASE
    final_plan["Server"]["port"].bind(8080)
    # print(final_plan['Server']['port'])
    final_plan["Server"]["port"].execute(db)

    print(final_plan["Server"]["port"].view(db))

    final_plan["Server"]["alive_time"].bind({"minute": 29, "second": 20})

    final_plan["Server"]["alive_time"].execute(db)
    # print(final_plan['Server']['alive_time'])
    print(final_plan["Server"]["alive_time"].view(db))

    final_plan["Server"]["commands"].bind(
        [
            {
                "name": "sample name",
                "description": "sample description",
            },
            {
                "name": "sample name2",
                "description": "sample description2",
            },
        ]
    )
    # print(final_plan['Server']['commands'])
    final_plan["Server"]["commands"].execute(db)

    print(final_plan["Server"]["commands"].view(db))

    db.close()
