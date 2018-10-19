#!/usr/bin/env python

"""yaml2cli: Script Generator that organizes cli args by YAML

See:
https://github.com/ickc/yaml2cli
"""

import argparse
import os
from collections import OrderedDict
from functools import partial
import sys
import yaml
import yamlordereddictloader
from itertools import product, islice, takewhile, count

__version__ = '1.0.1'


def make_executable(path):
    mode = os.stat(path).st_mode
    # copy r bits to x
    mode |= (mode & 0o444) >> 2
    os.chmod(path, mode)


def option2arg(option, var=None, loop=None, branch=None):
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
    def get_value(value, branch=None, yaml_globals=None, yaml_locals=None):
        local_value = value[branch] if isinstance(value, dict) else value
        if isinstance(local_value, str) and local_value.startswith('eval '):
            local_value = eval(local_value[5:], yaml_globals, yaml_locals)
        return local_value

    def key_value_to_arg(key, value, branch=None, yaml_globals=None, yaml_locals=None):
        '''return arg will be the cli in list form

        >>> key_value_to_arg('b', ['value1', 'value2'])
        ['-b', 'value1', 'value2']
        >>> key_value_to_arg('--flag', None)
        ['--flag']
        '''
        result = ['-' + key if len(key) == 1 else '--' + key]

        local_value = get_value(value, branch, yaml_globals, yaml_locals)

        if isinstance(local_value, list):
            result += [str(local_value_i) for local_value_i in local_value]
        elif local_value is not None:
            result.append(str(local_value))
        # local_value == None is defined as the case that the arg does not
        # require an option
        return result

    def arg_list_to_arg_str(option, keys, values, branch=None, yaml_globals=None):
        '''keys, values are those of the loop variables
        '''
        yaml_locals = {
            key: get_value(value, branch, yaml_globals)
            for key, value in zip(keys, values)
        } if keys else {}
        # arg will be something like ['-b', 'value1', 'value2', '--flag']
        arg = []
        # Cases for value of option
        for key, value in option.items():
            arg += key_value_to_arg(key, value, branch, yaml_globals, yaml_locals)
        return ' '.join(arg)

    yaml_globals = {} if var is None else {
        key: get_value(value, branch)
        for key, value in var.items()
    }

    # get keys, values from loop
    loop_key_values = {} if loop is None else OrderedDict(
        (key, get_value(value, branch, yaml_globals))
        for key, value in loop.items()
    )

    # each element of args is one single command
    # e.g. '-b value1 value2 --flag'
    # loop through Cartesian product of values
    # If loop_key_values is {}, then run exactly once
    args = map(
        partial(
            arg_list_to_arg_str,
            option,
            loop_key_values.keys(),
            branch=branch,
            yaml_globals=yaml_globals
        ),
        product(*loop_key_values.values())
    )
    return list(args)


def dict2command(arg_dict, branch=None):
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
        for arg in option2arg(option, var=arg_dict.get('var', None), loop=arg_dict.get('loop', None), branch=branch):
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
    '''
    metadata = yaml.load(args.yaml, Loader=yamlordereddictloader.Loader)
    script = args.path.read() if args.path else ''
    modes = flatten_list(metadata, args.mode)
    command_iter = (command for mode in modes for command in dict2command(metadata[mode], args.branch))
    if args.outdir is None:
        args.output.write(script + '\n' + '\n'.join(command_iter) + '\n')
        if args.output.name != '<stdout>':
            make_executable(args.output.name)
    else:
        if not os.path.isdir(args.outdir):
            os.makedirs(args.outdir)
        # a list where each element is N commands
        N_commands_iter = command_iter if args.N == 1 else \
            takewhile(bool, ('\n'.join(list(islice(command_iter, args.N))) for _ in count(0)))
        for i, command in enumerate(N_commands_iter):
            i_padded = str(i).zfill(args.digit)
            filepath = os.path.join(args.outdir, args.name + '-' + i_padded + '.sh')
            with open(filepath, 'w') as f:
                f.write(script.format(i_padded, args.name) + '\n' + command + '\n')
            make_executable(filepath)


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
    parser.add_argument('-d', '--outdir',
                        help='If used, ignore -o and stdout, output a script per N command.')
    parser.add_argument('-N', type=int, default=1,
                        help='Number of jobs per script. Used with -d.')
    parser.add_argument('-n', '--name', default='job',
                        help='Must be used with -d. Job no. and .sh will be appended.')
    parser.add_argument('-D', '--digit', type=int, default=4,
                        help='Must be used with -d. The no. of zero-filled digits. Default: 4. i.e. filename will be ...-0000.sh')
    parser.add_argument('-y', '--yaml', type=argparse.FileType('r'),
                        help='YAML metadata.', required=True)
    parser.add_argument('-p', '--path', type=argparse.FileType('r'),
                        help='shell script that prepends the commands. If -d is used, 2 format strings can be supplied optionally.')
    parser.add_argument('-H', '--branch',
                        help='The branch that the output script is going to be run on, as a sub-key-value pairs under options.')

    # parsing and run main
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
