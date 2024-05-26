import sys
import pickle
import subprocess

from evaluator import *
from utils import TriggerException

# struct that hold IO plan for each config
final_plan: Dict[str, Dict[str, Plan]] = dict()

cur_trigger_name = None


def GET(field_dir: str) -> list:
    config_n, field_n = field_dir.split('.')

    try:
        field_plan = final_plan[config_n][field_n]
    except KeyError:
        raise CanfigException(f"trigger '{cur_trigger_name}' fail due to field '{field_dir}' not exist")

    return field_plan.view(db)


def SET(field_dir: str, values) -> None:
    config_n, field_n = field_dir.split('.')

    try:
        field_plan = final_plan[config_n][field_n]
    except KeyError:
        raise CanfigException(f"trigger '{cur_trigger_name}' fail due to field '{field_dir}' not exist")

    field_plan.bind(values)
    field_plan.execute(db)


def CANFIG_ERR(msg: str):
    raise TriggerException(msg)


def CANFIG_WARN(msg: str):
    print(f"Trigger Warning: {msg}")


def ASSERT_REGEX(target, pattern: bytes):
    if not target:
        return None
    if not re.match(pattern, target):
        return f"Value '{target}' does not match the pattern '{pattern}'"
    return None


# Assert function for equality check
def ASSERT_EQUAL(target, dest):
    return target == dest


# Assert function for uniqueness
def ASSERT_UNIQUE(list, getter):
    seen = set()
    for item in list:
        value = getter(item)
        if value in seen:
            return f"Duplicate value found: '{value}'"
        seen.add(value)
    return None


def format_code(code_string):
    # Split the code string into lines
    lines = code_string.split('\n')

    # Remove 2 spaces of indentation from each line
    unindented_lines = [line[4:] if line.startswith('    ') else line for line in lines]

    # Join the lines back into a single string
    return '\n'.join(unindented_lines)


if __name__ == '__main__':
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

    # Registering Phase
    for trigger_info in cplan_data['triggers']:
        assert trigger_info[
                   'condition'] in final_plan, f"fail to register Trigger '{trigger_info['name']} " \
                                               f"" \
                                               f"due to Config {trigger_info['condition']}' not exist"

        for field_name, field_plan in final_plan[trigger_info['condition']].items():
            field_plan.add_trigger(trigger_info['name'], format_code(trigger_info['cmd']), globals())
            print(f"register trigger '{trigger_info['name']}' for '{field_name}'")

    # # TEST CASE
    final_plan["Server"]["port"].bind(8128)
    print(final_plan['Server']['port'])
    final_plan["Server"]["port"].execute(db)

    print(final_plan["Server"]["port"].view(db))
    #
    # final_plan["Server"]["alive_time"].bind({"minute": 29, "second": 20})
    #
    # final_plan["Server"]["alive_time"].execute(db)
    # print(final_plan['Server']['alive_time'])
    # print(final_plan["Server"]["alive_time"].view(db))
    #
    # final_plan["Server"]["commands"].bind(
    #     [
    #         {
    #             "name": "sample name",
    #             "description": "sample description",
    #         },
    #         {
    #             "name": "sample name2",
    #             "description": "sample description2",
    #         },
    #     ]
    # )
    # print(final_plan['Server']['commands'])
    # final_plan["Server"]["commands"].execute(db)
    #
    # print(final_plan["Server"]["commands"].view(db))
    #
    # final_plan["Server"]["alive_time"].bind(
    #     {
    #         "minute": 12,
    #         "second": 12,
    #     }
    # )
    # final_plan["Server"]["alive_time"].execute(db)
    # print(final_plan["Server"]["alive_time"])

    db.close()
