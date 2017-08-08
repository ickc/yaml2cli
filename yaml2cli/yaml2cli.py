#!/usr/bin/env python

"""yaml2cli: Script Generator that organizes cli args by YAML

See:
https://github.com/ickc/yaml2cli
"""

import argparse
import sys
import yaml
import yamlordereddictloader
from itertools import product


__version__ = '0.5.1'


def option2arg(option, var, loop, host='cori'):
    '''Covert options as a Python dictionary to a string in cli arg style.

    Parameters
    ----------
    option: dict
        spec:
            - keys are the cli options. Single letter will be appended ``-``,
            otherwise ``--``
            - values are either list, dict, None, or string-like.
                - for list, it becomes multiple argument of the option.
                - for dict, its key will be used to lookup the host.
                - for None, it will be skipped. Useful for cli flag.
                - for others, it will be converted to string.
    var: dict
        each key-value pair are exec into a variable with value
    loop: dict
        All values are list, or eval to a list.
        Values of all keys forms a Cartesian product.
        They behaves like nested loops where each key (variables) loop through all values.
    host: str

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
            if isinstance(value, str):
                exec(key + ' = "' + value + '"')
            else:
                exec(key + ' = ' + str(value))

    # get all keys and all values into separate lists
    values = []
    if loop is not None:
        keys = []
        for key, value in loop.items():
            keys.append(key)
            # Cases for value of loop
            if isinstance(value, list):
                values.append(value)
            # eval if the string start with eval
            elif isinstance(value, str) and value[0:5] == 'eval ':
                values.append(eval(value[5:]))
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
            if isinstance(value, list):
                arg += value
            elif isinstance(value, dict):
                try:
                    arg.append(str(value[host]))
                except KeyError:
                    sys.stderr.write('Host {} is not supported.'.format(host))
            # eval if the string start with eval
            elif isinstance(value, str) and value[0:5] == 'eval ':
                arg.append(eval(value[5:]))
            elif value is not None:
                arg.append(str(value))
        args.append(' '.join(arg))
    return args


def dict2command(arg_dict, host='cori'):
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
    >>> dict2command(arg_dict, host='cori')
        ['my_program --flag --test case1 case2 -c 10 -n 3']
    '''
    commands = []
    for option in arg_dict['option']:
        for arg in option2arg(option, arg_dict.get('var', None), arg_dict.get('loop', None), host):
            commands.append(arg_dict['command'] + ' ' + arg)
    return commands


def script_generator(modes, script, metadata):
    '''
    Parameters
    ----------
    modes: list of string
    script: string
        to be prepended to the commands
    metadata: dict
        a dict with keys of each mode in modes,
        with values defined according to the spec in dict2command

    Return
    ------
    str
        a shell script
    '''
    command_list = []
    for mode in modes:
        command_list += dict2command(metadata[mode])
    return script + '\n' + '\n'.join(command_list) + '\n'


def main(args):
    '''load the script and yaml specfied in args
    output a shell script
    remember to ``chmod +x`` the output file
    '''
    metadata = yaml.load(args.yaml, Loader=yamlordereddictloader.Loader)
    script = args.path.read() if args.path else ''
    # get modes. metadata might contains shortcuts to a list of modes
    # TODO: do this recursively
    modes = []
    for mode in args.mode:
        if isinstance(metadata[mode], list):
            modes += metadata[mode]
        else:
            modes.append(mode)

    args.output.write(script_generator(modes, script, metadata))


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
    parser.add_argument('-H', '--host', required=True,
                        help='The host that the output script is going to be run on.')

    # parsing and run main
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
