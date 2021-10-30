import warnings
import copy
import inspect
from collections import Callable, Iterable, Mapping

def identity_map(*args, **kwargs):
    if kwargs == {}:
        if len(args) == 1:
            return args[0]
        else:
            return args
    return args, kwargs

def _check_callable(x):
    # None なら恒等関数にするのでよし
    # あとは Callable か、Callable のリストでなければエラー
    if x is None:
        return
    if isinstance(x, Callable):
        return
    elif isinstance(x, list):
        for f in x:
            if not isinstance(f, Callable):
                raise ValueError(f"uncallable object '{f}' in the list, which must be 'Callable' or 'List[Callable]'.")
    else:
        raise ValueError("function must be 'Callable' or 'List[Callable]'.")

def _expand(args, kwargs={}):
    if kwargs != {}:
        return args, kwargs

    _args = args
    _kwargs = {}

    if isinstance(args, tuple):
        if len(args) == 2 and isinstance(args[0], tuple) and isinstance(args[1], dict):
            # 戻り値がタプルと辞書の組のときは展開
            _args = args[0]
            _kwargs = args[1]
        elif len(args) == 1 and isinstance(args[0], tuple):
            # 戻り値がタプルのときは展開
            _args = args[0]
    return _args, _kwargs
        
def _get_args(function, params, args, kwargs, partial_args={}):
    partial_args = copy.copy(partial_args)
    if len(args) > len(params):
        # this function call raises TypeError
        function(*args, **kwargs)
    
    args = list(args)
    _args = []
    for (k, v) in params.items():
        if len(args) == 0:
            break
        if k in partial_args:
            _args.append(partial_args[k])
        else:
            arg = args.pop(0)
            _args.append(arg)
            partial_args[k] = arg
    
    if len(args) > 0:
        args = _args + args
        # this function call raises TypeError
        function(*args, **kwargs)
    
    for k, v in kwargs.items():
        if k in partial_args:
            raise TypeError(f"{function.__name__} got multiple values for argument '{k}'")
        if k not in params:
            raise TypeError(f"{function.__name__} got an unexpected keyword argument '{k}'")
        partial_args[k] = v

    return partial_args
        
def _merge_args(params, partial_args):
    ret_args = {}
    for k, v in partial_args.items():
        ret_args[k] = v
    for k, v in params.items():
        if v.default != inspect._empty and k not in ret_args:
            ret_args[k] = v.default
    
    return ret_args

class Chain:
    def __init__(self, function=None, *args, **kwargs):
        _check_callable(function)

        # チェーンさせる関数をリストで保持しておく
        if function is None:
            self.function = [identity_map]
        elif isinstance(function, list):
            self.function = copy.copy(function)
        else:
            self.function = [function]
        
        if isinstance(self.function[0], Chain):
            self._params = self.function[0]._params
        elif isinstance(self.function[0], Callable):
            self._params = dict(inspect.signature(self.function[0]).parameters)
        else:
            raise ValueError('unknown error')

        self._args = _get_args(function, self._params, args, kwargs, partial_args={})
        self._params = { k: v for k, v in self._params.items() if k not in self._args }
    
    def __call__(self, *args, **kwargs):
        _args, _kwargs = _expand(args, kwargs)

        # currying
        partial_args = _get_args(self.function[0], self._params, _args, _kwargs, self._args)
        merged_args = _merge_args(self._params, partial_args)

        if len(merged_args) < len(self._params):
            return Chain(self, **partial_args)

        f_idx = 0
        
        # 途中で None になったらそこでチェーンが切れているので警告
        def check_arg(x):
            if x is None:
                warnings.warn(f"Chain broken with 'None' value between '{self.function[f_idx-1].__name__}' and '{self.function[f_idx].__name__}'", RuntimeWarning)
        
        chain_args = self.function[0](**merged_args)
        for f_idx, f in enumerate(self.function[1:], 1):
            check_arg(chain_args)

            if not isinstance(chain_args, tuple):
                chain_args = f(chain_args)
            elif isinstance(f, Chain):
                chain_args = f(chain_args)
            else:
                _args, _kwargs = _expand(chain_args)
                chain_args = f(*_args, **_kwargs)
        return chain_args
    
    # f * g
    def __mul__(self, other):
        if isinstance(other, Chain):
            return Chain([other, self])
        if isinstance(other, Callable):
            return Chain([other, self])
        raise ValueError("uncallable object can't be chained.")
    
    # f >> g
    def __rshift__(self, other):
        if isinstance(other, Chain):
            return Chain([self, other])
        if isinstance(other, Callable):
            return Chain([self, other])
        raise ValueError("uncallable object can't be chained.")
    
    # f | x
    def __or__(self, other):
        return self(other)

    # f & x
    def __and__(self, other):
        if isinstance(other, Mapping):
            return self(**other)
        if isinstance(other, Iterable):
            return self(*other)
        return self(other)
    
    # 左辺が Chain でないときの f >> g
    def __rrshift__(self, other):
        return self(other)

    # 左辺が Chain でないときの x | f
    def __ror__(self, other):
        return self(other)

    # 左辺が Chain でないときの x & f
    def __rand__(self, other):
        if isinstance(other, Mapping):
            return self(**other)
        if isinstance(other, Iterable):
            return self(*other)
        return self(other)

# デコレータ
def chain(function):
    return Chain(function)

# 恒等関数
L = Chain()