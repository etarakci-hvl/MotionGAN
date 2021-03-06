from __future__ import absolute_import, division, print_function
from contextlib import contextmanager


class Scoping:
    def __init__(self):
        self._name_stack = ''

    @staticmethod
    def get_global_scope():
        global_scope = None
        for val in globals().values():
            if isinstance(val, Scoping):
                global_scope = val

        if global_scope is not None:
            return global_scope
        else:
            global scoping
            scoping = Scoping()
            return scoping

    @contextmanager
    def name_scope(self, scope):
        try:
            old_stack = self._name_stack
            if self._name_stack == '':
                self._name_stack = scope
            else:
                self._name_stack += '/' + scope
            yield self._name_stack
        finally:
            self._name_stack = old_stack

    def __str__(self):
        return self._name_stack

    def __add__(self, other):
        return str(self) + '/' + str(other)


def scope_wrapper(func, *args, **kwargs):
    """Create a name scope around the function with its name.
       Note: This decorator requires the scope keyword argument
       in the signature of the target function"""
    def scoped_func(*args, **kwargs):
        scope = Scoping.get_global_scope()
        with scope.name_scope(func.__name__):
            kwargs['scope'] = scope
            return func(*args, **kwargs)
    return scoped_func


if __name__ == "__main__":
    scope = Scoping.get_global_scope()

    def _test_global():
        my_scopex = Scoping.get_global_scope()
        print('global test:', my_scopex)

    with scope.name_scope('foo') as foo_scope:
        print(scope)
        print(foo_scope)
        with scope.name_scope('bar'):
            print(scope)
            print(foo_scope)
            with scope.name_scope('baz'):
                print(scope)
                _test_global()
                print('str add test:', scope + 123)

            print(scope)
        print(scope)
    print(scope)
