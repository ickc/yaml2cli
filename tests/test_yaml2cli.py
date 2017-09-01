"""
"""
from .context import option2arg, dict2command, flatten_list
from collections import OrderedDict


def test_option2arg():
    option = OrderedDict([('n', 3),
                          ('test', ['case1', 'case2']),
                          ('c', OrderedDict([('cori', 10), ('gordita', 1)])),
                          ('flag', None)])
    assert option2arg(option, None, None, 'cori') == [
        '-n 3 --test case1 case2 -c 10 --flag']


def test_dict2command():
    arg_dict = OrderedDict([('command', 'my_program'),
                            ('option',
                             [OrderedDict([('c', OrderedDict([('cori', 10), ('gordita', 1)])),
                                           ('flag', None),
                                           ('n', 3),
                                           ('test', ['case1', 'case2'])])])])
    assert dict2command(arg_dict, 'cori') == [
        'my_program -c 10 --flag -n 3 --test case1 case2']


def test_flatten_list():
    metadata = {
        'a': ['b', 'c'],
        'b': ['d', 'e'],
        'c': 1,
        'd': ['f', 'g'],
        'e': 1,
        'f': 1,
        'g': 1
    }
    assert flatten_list(metadata, 'a') == ['f', 'g', 'e', 'c']
