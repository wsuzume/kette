import warnings
import copy
import inspect
from collections import Callable, Iterable, Mapping

def identity_map(x):
    return x

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
    def __init__(self, __function__=None, *args, **kwargs):
        _check_callable(__function__)

        # チェーンさせる関数をリストで保持しておく
        if __function__ is None:
            self.function = [identity_map]
        elif isinstance(__function__, list):
            self.function = list(map(signaturize, __function__))
        else:
            self.function = [signaturize(__function__)]
        
        self.__name__ = self.function[0].__name__ + '_chain'
        
        if isinstance(self.function[0], Chain):
            self._params = self.function[0]._params
        elif isinstance(self.function[0], Callable):
            self._params = dict(inspect.signature(self.function[0]).parameters)
        else:
            raise ValueError('unknown error')

        self._args = _get_args(self.function[0], self._params, args, kwargs, partial_args={})
        self._params = { k: v for k, v in self._params.items() if k not in self._args }
    
    def __call__(self, *args, **kwargs):
        # currying
        partial_args = _get_args(self.function[0], self._params, args, kwargs, self._args)
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
            else:
                _args, _kwargs = _expand(chain_args)
                chain_args = f(*_args, **_kwargs)
        return chain_args
    
    # f * g
    def __mul__(self, other):
        if isinstance(other, Chain):
            return Chain([other, self])
        if isinstance(other, Callable):
            return Chain([signaturize(other), self])
        raise ValueError("uncallable object can't be chained.")
    
    # f >> g
    def __rshift__(self, other):
        if isinstance(other, Chain):
            return Chain([self, other])
        if isinstance(other, Callable):
            return Chain([self, signaturize(other)])
        raise ValueError("uncallable object can't be chained.")
    
    # f | x
    def __or__(self, other):
        if isinstance(other, Mapping):
            return self(**other)
        if isinstance(other, Iterable):
            return self(*other)
        return self(other)

    # f & x
    def __and__(self, other):
        return self(other)
    
    # 左辺が Chain でないときの f >> g
    def __rrshift__(self, other):
        return self(other)

    # 左辺が Chain でないときの x | f
    def __ror__(self, other):
        if isinstance(other, Mapping):
            return self(**other)
        if isinstance(other, Iterable):
            return self(*other)
        return self(other)

    # 左辺が Chain でないときの x & f
    def __rand__(self, other):
        return self(other)

# デコレータ
def chain(__function, *args, **kwargs):
    return Chain(__function, *args, **kwargs)

# 恒等関数
L = Chain()

def signaturize(fun):
    if not inspect.ismethod(fun) and fun.__name__ in _BUILTIN_FUNCS:
        return _BUILTIN_FUNCS[fun.__name__]
    return fun

# builtin functions
import sys

_c_abs = lambda x: abs(x)
# _c_aiter = lambda async_iterable: aiter(async_iterable)
_c_all = lambda iterable: all(iterable)
_c_any = lambda iterable: any(iterable)
_c_ascii = lambda obj: ascii(obj)
_c_bin = lambda x: bin(x)
_c_bool = lambda x=None: bool(x)
_c_bytearray = lambda source=b'', encoding=sys.getdefaultencoding(), errors='strict': bytearray(source, encoding, errors)
_c_bytes = lambda source=b'', encoding=sys.getdefaultencoding(), errors='strict': bytes(source, encoding, errors)
_c_callable = lambda obj: callable(obj)
_c_chr = lambda i: chr(i)
_c_compile = lambda source, filename, mode, flags=0, dont_inherit=False, optimize=-1: compile(source, filename, mode, flags, dont_inherit, optimize)
_c_complex = lambda real=0, imag=0: complex(real, imag)
# _c_delattr = lambda obj, name: delattr(obj, name)
_c_dict = lambda obj: dict(obj)
# FROM Python 3.10 -> _c_dict = lambda obj={}, /, **kwargs: dict(obj, kwargs)
# _c_dir
_c_divmod = lambda a, b: divmod(a, b)
_c_enumerate = lambda iterable, start=0: enumerate(iterable, start)
# _c_eval
# _c_exec
_c_filter = lambda fun, iterable: filter(fun, iterable)
_c_float = lambda x=0: float(x)
# _c_format
_c_flozenset = lambda iterable=(): frozenset(iterable)
# _c_getattr = lambda obj, name[, default]: getattr(obj, name, default)
# _c_globals
# _c_hasattr
_c_hash = lambda obj: hash(obj)
# _c_help
_c_hex = lambda x: hex(x)
_c_id = lambda obj: id(obj)
# _c_input
_c_int = lambda x=0, base=10: int(x, base)
_c_isinstance = lambda obj, classinfo: isinstance(obj, classinfo)
_c_issubclass = lambda cls, classinfo: issubclass(cls, classinfo)
# _c_iter
_c_len = lambda s: len(s)
_c_list = lambda iterable=(): list(iterable)
_c_map = lambda fun, iterable: map(fun, iterable)
# _c_max
# _c_min
# _c_next
# _c_object
_c_oct = lambda x: oct(x)
# _c_open
_c_ord = lambda x: ord(x)
# _c_pow
# _c_print
# _c_property
# _c_range
_c_repr = lambda obj: repr(obj)
_c_reversed = lambda seq: reversed(seq)
_c_round = lambda number, ndigits=None: round(number, ndigits)
_c_set = lambda iterable=(): set(iterable)
# _c_setattr
# _c_slice
_c_sorted = lambda iterable, *, key=None, reverse=False: sorted(iterable, key=key, reverse=reverse)
_c_str = lambda obj=b'', encoding='utf-8', errors='strict': str(obj, encoding, errors)
_c_sum = lambda iterable, start=0: sum(iterable, start)
# FROM Python 3.10 -> _c_sum = lambda iterable, /, start=0: sum(iterable, start)
# _c_super
_c_tuple = lambda iterable=(): tuple(iterable)
# _c_type
# _c_vars
# _c_zip = lambda *iterables: zip(*iterables)
#FROM Python 3.10 -> _c_zip = lambda *iterables, strict=False: zip(*iterables, strict=strict)

_BUILTIN_FUNCS = {
    'abs': _c_abs,
    # 'aiter': _c_aiter,
    'all': _c_all,
    'any': _c_any,
    'ascii': _c_ascii,
    'bin': _c_bin,
    'bool': _c_bool,
    'bytearray': _c_bytearray,
    'bytes': _c_bytes,
    'callable': _c_callable,
    'chr': _c_chr,
    'compile': _c_compile,
    'complex': _c_complex,
    # 'delattr': _c_delattr,
    'dict': _c_dict,
    # 'dir': _c_dir,
    'divmod': _c_divmod,
    'enumerate': _c_enumerate,
    # 'eval': _c_eval,
    # 'exec': _c_exec,
    'filter': _c_filter,
    'float': _c_float,
    # 'format': _c_format,
    'frozenset': _c_flozenset,
    # 'getattr': _c_getattr,
    # 'globals': _c_globals,
    # 'hasattr': _c_hasattr,
    'hash': _c_hash,
    # 'help': _c_help,
    'hex': _c_hex,
    'id': _c_id,
    # 'input': _c_input,
    'int': _c_int,
    'isinstance': _c_isinstance,
    'issubclass': _c_issubclass,
    # 'iter': _c_iter,
    'len': _c_len,
    'list': _c_list,
    'map': _c_map,
    # 'max': _c_max,
    # 'min': _c_min,
    # 'next': _c_next,
    # 'object': _c_object,
    'oct': _c_oct,
    # 'open': _c_open,
    'ord': _c_ord,
    # 'pow': _c_pow,
    # 'print': _c_print,
    # 'property': _c_property,
    # 'range': _c_range,
    'repr': _c_repr,
    'reversed': _c_reversed,
    'round': _c_round,
    'set': _c_set,
    # 'setattr': _c_setattr,
    # 'slice': _c_slice,
    'sorted': _c_sorted,
    'str': _c_str,
    'sum': _c_sum,
    # 'super': _c_super,
    'tuple': _c_tuple,
    # 'type': _c_type,
    # 'vars': _c_vars,
    # 'zip': _c_zip,
}