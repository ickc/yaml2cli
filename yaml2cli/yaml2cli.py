#!/usr/bin/env python

"""yaml2cli: Script Generator that organizes cli args by YAML

See:
https://github.com/ickc/yaml2cli
"""

import argparse
import os
import sys
import yaml
import yamlordereddictloader
from itertools import product


__version__ = '0.5.4'


def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    os.chmod(path, mode)


def option2arg(option, var, loop, branch):
    '''Covert options as a Python dictionary to a string in cli arg style.

    Parameters
    ----------
    option: dict
        spec:
            - keys are the cli options. Single letter will be appended ``-``,
            otherwise ``--``
            - values are either list, dict, None, or string-like.
                - for list, it becomes multiple argument of the option.
                - for dict, its key will be used to lookup the branch.
                - for None, it will be skipped. Useful for cli flag.
                - for others, it will be converted to string.
    var: dict
        each key-value pair are exec into a variable with value
    loop: dict
        All values are list, or eval to a list.
        Values of all keys forms a Cartesian product.
        They behaves like nested loops where each key (variables) loop through all values.
    branch: str

    Return
    ------
    str
        A string of the command line arguments

    Example
    -------
    >>> option = {'n': 3, 'test': ['case1', 'case2'],
                  'c': {'cori': 10, 'gordita': 1}, 'flag': None}
    >>> option2arg(option, None, None, 'cori')
    '--flag --test case1 case2 -c 10 -n 3'
    '''
    args = []

    # exec all var
    if var is not None:
        for key, value in var.items():
            if isinstance(value, dict):
                local_value = value[branch]
            else:
                local_value = value
            if isinstance(local_value, str):
                exec(key + ' = "' + local_value + '"')
            else:
                exec(key + ' = ' + str(local_value))

    # get all keys and all values into separate lists
    values = []
    if loop is not None:
        keys = []
        for key, value in loop.items():
            keys.append(key)
            # Cases for value of loop
            if isinstance(value, dict):
                local_value = value[branch]
            else:
                local_value = value
            if isinstance(local_value, list):
                values.append(local_value)
            # eval if the string start with eval
            elif isinstance(local_value, str) and local_value[0:5] == 'eval ':
                values.append(eval(local_value[5:]))
        n = len(keys)
    # loop through combinations. If values is [], then run exactly once
    for combinations in product(*values):
        # only evaluate loop when loop is not None
        if loop is not None:
            for i in range(n):
                if isinstance(combinations[i], str):
                    exec(keys[i] + ' = "' + combinations[i] + '"')
                else:
                    exec(keys[i] + ' = ' + str(combinations[i]))
        arg = []
        # Cases for value of option
        for key, value in option.items():
            arg.append('-' + key if len(key) == 1 else '--' + key)
            if isinstance(value, dict):
                try:
                    local_value = value[branch]
                except KeyError:
                    sys.stderr.write('Branch {} is not supported.'.format(branch))
            else:
                local_value = value
            if isinstance(local_value, list):
                arg += local_value
            # eval if the string start with eval
            elif isinstance(local_value, str) and local_value[0:5] == 'eval ':
                arg.append(eval(local_value[5:]))
            elif local_value is not None:
                arg.append(str(local_value))
        args.append(' '.join(arg))
    return args


def dict2command(arg_dict, branch):
    '''Covert a dictionary with a predefined spec to a list of commands to be
        run in shell

    Parameters
    ----------
    arg_dict: dict
        spec:
            - has key ``command``, with value as a string, the name of the
              command
            - has key ``option``, with value as a list. Each element in the
              list respect the spec defined in option2arg

    Return
    ------
    list of str
        A list of strings, where each is a command with args to be run in shell

    Example
    -------
    >>> arg_dict = {'command': 'my_program',
                    'option': [{'n': 3, 'test': ['case1', 'case2'],
                                'c': {'cori': 10, 'gordita': 1},
                                'flag': None}]}
    >>> dict2command(arg_dict, branch='cori')
        ['my_program --flag --test case1 case2 -c 10 -n 3']
    '''
    commands = []
    for option in arg_dict['option']:
        for arg in option2arg(option, arg_dict.get('var', None), arg_dict.get('loop', None), branch):
            commands.append(arg_dict['command'] + ' ' + arg)
    return commands


def flatten_list(metadata, modes):
    '''get modes recursively. metadata might contains shortcuts to a list of modes
    '''
    modes_flattened = []
    for mode in modes:
        if isinstance(metadata[mode], list):
            modes_flattened += flatten_list(metadata, metadata[mode])
        else:
            modes_flattened.append(mode)
    return modes_flattened


def main(args):
    '''load the script and yaml specfied in args
    output a shell script
    remember to ``chmod +x`` the output file
    '''
    metadata = yaml.load(args.yaml, Loader=yamlordereddictloader.Loader)
    script = args.path.read() if args.path else ''
    modes = flatten_list(metadata, args.mode)
    command_list = (command for mode in modes for command in dict2command(metadata[mode], args.branch))
    args.output.write(script + '\n' + '\n'.join(command_list) + '\n')


def cli():
    parser = argparse.ArgumentParser(description='Script Generator that organizes cli args by YAML.')
    parser.set_defaults(func=main)

    # define args
    parser.add_argument('mode', nargs='+',
                        help='The mode of the script generated.')
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s {}'.format(__version__))
    parser.add_argument('-o', '--output', type=argparse.FileType('w'),
                        help='output script', default=sys.stdout)
    parser.add_argument('-y', '--yaml', type=argparse.FileType('r'),
                        help='YAML metadata.', required=True)
    parser.add_argument('-p', '--path', type=argparse.FileType('r'),
                        help='shell script that define the paths.')
    parser.add_argument('-H', '--branch', required=True,
                        help='The branch that the output script is going to be run on, as a sub-key-value pairs under options.')

    # parsing and run main
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
