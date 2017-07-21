"""
"""
from .context import option2arg
from collections import OrderedDict


def test_option2arg():
    option = OrderedDict([('n', 3),
                          ('test', ['case1', 'case2']),
                          ('c', OrderedDict([('cori', 10), ('gordita', 1)])),
                          ('flag', None)])
    assert option2arg(option, None, None, 'cori') == [
        '-n 3 --test case1 case2 -c 10 --flag']
