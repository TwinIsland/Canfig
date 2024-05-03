"""
This is a Toy interpreter for Canfig Language, Not put in Production environment

In the future, I'll put the parsing and evaluating process in OCaml

"""

import sys
import os
import subprocess
from typing import List
import re
import pickle
import hashlib

from common import Token, TokenType, TagTokenType
from utils import *

from transitions import Machine
from enum import Enum, auto

BUF_SIZE = 65536  # file read buf
md5 = hashlib.md5()

# parse result
meta_data: dict = {}
sql_query: list = []
triggers: list = []
slices: list = []


class HandleFlag(Enum):
    STRUCT = auto()
    CONFIG = auto()
    TRIGGER = auto()
    SLICE = auto()
    NONE = auto()


class Parser(object):
    states = [token._name_ for token in TokenType] + \
             ['start', 'error'] + \
             ['do_push_kv', 'do_sql', 'do_pre_sql', 'do_slice']

    def __init__(self):
        self.kv_prev_state = ''
        self.state_buffer = ''

        self.ident_buffer = ''
        self.arg_buffer = ''

        self.err_msg = ''

        self.cur_handling = HandleFlag.NONE

        self.machine = Machine(model=self, states=Parser.states, initial='start')

        # start state -> *
        for state in self.states:
            self.machine.add_transition(trigger=state, source='start', dest=state)

        # next command
        self.machine.add_transition(trigger='SEMI', source='*', dest='start')

        # tag token handling
        for tag_state in [token._name_ for token in TagTokenType]:
            self.machine.add_transition(trigger='STRING', source=tag_state, dest='do_push_kv',
                                        before='push_kv', after='push_kv')

        # struct handling
        self.machine.add_transition(trigger='IDENT', source='STRUCT', dest='IDENT', after='struct_handler')
        self.machine.add_transition(trigger='IDENT', source='IDENT', dest='IDENT',
                                    after='edge_case_handler')  # edge case

        # argument handling
        self.machine.add_transition(trigger='ARGUMENT', source='IDENT', dest='ARGUMENT', after='arg_handler')

        # config handling
        self.machine.add_transition(trigger='IDENT', source='CONFIG', dest='IDENT', after='config_handler')

        # trigger handling
        self.machine.add_transition(trigger='IDENT', source='TRIGGER', dest='IDENT', after='trigger_handler')
        self.machine.add_transition(trigger='TRICOND', source='IDENT', dest='TRICOND')
        self.machine.add_transition(trigger='IDENT', source='TRICOND', dest='IDENT', before='trigger_handler')

        # slice handling
        self.machine.add_transition(trigger='IDENT', source='SLICE', dest='IDENT', after='slice_handler')

        # command handling
        self.machine.add_transition(trigger='COMMAND', source='IDENT', dest='COMMAND', before='command_handler')
        self.machine.add_transition(trigger='COMMAND', source='ARGUMENT', dest='COMMAND', before='command_handler')

        # reject all unexpected state
        for state in self.states:
            self.machine.add_transition(trigger=state, source='*', dest='error', before='raise_err')

        self.machine.add_transition(trigger='ERROR', source='*', dest='error', before='raise_err')

    def slice_handler(self):
        self.cur_handling = HandleFlag.SLICE
        self.ident_buffer = self.state_buffer

    def arg_handler(self):
        if self.cur_handling != HandleFlag.STRUCT:
            self.err_msg = "only STRUCT and TRIGGER type can have argument"
            self.ERROR()
        self.arg_buffer = self.state_buffer

    def config_handler(self):
        if self.state == 'IDENT':
            self.cur_handling = HandleFlag.CONFIG
            self.ident_buffer = self.state_buffer

    def struct_handler(self):
        if self.state == 'IDENT':
            self.cur_handling = HandleFlag.STRUCT
            self.ident_buffer = self.state_buffer

    def trigger_handler(self):
        if self.state == 'IDENT':
            self.cur_handling = HandleFlag.TRIGGER
            self.ident_buffer = self.state_buffer

        if self.state == 'TRICOND':
            if self.cur_handling != HandleFlag.TRIGGER:
                self.err_msg = "'WHEN CHANGE' can only use with Trigger"
                self.ERROR()

            self.ident_buffer += '|' + self.state_buffer

    def edge_case_handler(self):
        if self.cur_handling != HandleFlag.STRUCT:
            self.err_msg = "identifier cannot follow identifier"
            self.ERROR()
        else:
            sql_query.append({
                'name': self.ident_buffer,
                'sql': f"{self.ident_buffer} {self.state_buffer}",
                'pre': False,
                'type': 'STRUCT'
            })
            self.cur_handling = HandleFlag.NONE

    def command_handler(self):
        if self.cur_handling == HandleFlag.NONE:
            self.err_msg = 'command need to specified identifier'
            self.ERROR()

        elif self.cur_handling == HandleFlag.STRUCT and self.state == 'IDENT':
            sql_query.append({
                'name': self.ident_buffer,
                'sql': self.state_buffer,
                'pre': False,
                'type': 'STRUCT'
            })

        elif self.cur_handling == HandleFlag.STRUCT and self.state == 'ARGUMENT':
            sql_query.append({
                'name': self.ident_buffer,
                'sql': self.state_buffer,
                'pre': True,
                'arg': self.arg_buffer,
                'type': 'STRUCT'
            })

        elif self.cur_handling == HandleFlag.CONFIG:
            sql_query.append({
                'name': self.ident_buffer,
                'sql': self.state_buffer,
                'pre': True,
                'type': 'CONFIG'
            })

        elif self.cur_handling == HandleFlag.TRIGGER:
            name, condition = self.ident_buffer.split('|')
            triggers.append({
                'name': name,
                'condition': condition,
                'cmd': self.state_buffer
            })

        elif self.cur_handling == HandleFlag.SLICE:
            slices.append({
                'name': self.ident_buffer,
                'cmd': self.state_buffer
            })
        else:
            self.ERROR()

        self.ident_buffer = ''
        self.state_buffer = ''
        self.arg_buffer = ''
        self.cur_handling = HandleFlag.NONE

    def push_kv(self):
        if self.state != 'do_push_kv':
            self.kv_prev_state = self.state
        else:
            assert self.kv_prev_state != ''
            meta_data[self.kv_prev_state] = self.state_buffer
            self.kv_prev_state = ''

    def update_str_buffer(self, buf):
        self.state_buffer = buf

    def raise_err(self):
        raise Exception(f'parse error in state {self.state}! {self.err_msg}')


def lexing(from_file, to_file):
    if not check_file_exists("ast"):
        if not check_command_installed("make"):
            raise Exception("'make' not installed.")
        if not check_command_installed("ocamlc"):
            raise Exception("'ocamlc' not installed.")

        subprocess.run(['make', 'exe'])

    ret = subprocess.run(['./ast', from_file, '-o', to_file])
    if ret.returncode != 0:
        raise Exception("lexing fails.")
    print("lexing done.")


def tokenize(from_file) -> List[Token]:
    def process_str_token(str_token):
        pre_token = re.match(r'^([A-Z_]+)(?:\((.*)\))?$', str_token, re.DOTALL).groups()

        if pre_token[1] is None:
            return Token(getattr(TokenType, pre_token[0]))

        return Token(getattr(TokenType, pre_token[0]), pre_token[1])

    with open(from_file, 'r') as fptr:
        _tokens = fptr.read().split('[_!]')
        _tokens = list(map(process_str_token, _tokens))

        print(f'processing {len(_tokens)} tokens.')

        return _tokens


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        exit(1)

    if not check_file_exists(input_file := sys.argv[1]):
        raise FileNotFoundError(f"'{input_file}' no found.")

    with open(input_file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)

    # try to load candy
    if check_file_exists(cplan_file := input_file.split('.')[0] + '.candy'):
        with open(cplan_file, 'rb') as f:
            cdata = pickle.load(f)

        if md5.hexdigest() == cdata['md5']:
            print(f"find fresh candy '{cplan_file}'! No need to compile")
            exit(0)
        else:
            print(f"candy '{cplan_file}' find but out of date, recompile...")

    # lexing
    lexing(input_file, input_file.split('.')[0])
    tokens = tokenize(cando_file := input_file.split('.')[0] + '.cando')
    subprocess.run(['rm', cando_file])

    # parsing
    parser = Parser()
    for token in tokens:
        # print(parser.state, "   ", parser.cur_handling)
        if token.value is not None:
            parser.update_str_buffer(token.value)
        getattr(parser, token.type._name_)()

    print("parsing done.")
    print(
        f"meta data: {len(meta_data)}, struct/config: {len(sql_query)}, trigger: {len(triggers)}, slice: {len(slices)}")

    with open(cplan_file, 'wb') as f:
        pickle.dump({
            'md5': md5.hexdigest(),
            'meta_data': meta_data,
            'sql_query': sql_query,
            'triggers': triggers,
            'slices': slices
        }, file=f)

    print(f"dump '{input_file}' to plan '{cplan_file}'")
