import warnings
from collections import Callable, Iterable, Mapping

def identity_map(*args, **kwargs):
    if kwargs == {}:
        if len(args) == 1:
            return args[0]
        else:
            return args
    return args, kwargs

class Closure:
    def __init__(self, function, **kwargs):
        # kwargs が指定されたら保存しておく
        if not isinstance(function, Callable):
            raise ValueError('function must be callable.')
        self.function = function
        self.kwargs = kwargs
    
    def __call__(self, *args, **kwargs):
        # 関数呼び出し時に保存していた kwargs を使う
        # 新しい kwargs が指定されていたら上書きしておく
        for k, v in kwargs.items():
            self.kwargs[k] = v
        return self.function(*args, **self.kwargs)

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

class Chain:
    def __init__(self, function=None):
        _check_callable(function)

        # チェーンさせる関数をリストで保持しておく
        if function is None:
            self.function = identity_map
        elif isinstance(function, list):
            self.function = function
        else:
            self.function = [function]
    
    def __call__(self, *args, **kwargs):
        f_idx = 0
        
	# 途中で None になったらそこでチェーンが切れているので警告
        def check_arg(x):
            if x is None:
                warnings.warn(f"Chain broken with 'None' value between '{self.function[f_idx-1].__name__}' and '{self.function[f_idx].__name__}'", RuntimeWarning)
        
        chain_args = self.function[0](*args, **kwargs)
        for f_idx, f in enumerate(self.function[1:], 1):
            check_arg(chain_args)
            if isinstance(chain_args, tuple):
                if len(chain_args) == 2 and isinstance(chain_args[0], tuple) and isinstance(chain_args[1], dict):
                    # 戻り値がタプルと辞書の組のときは展開
                    chain_args = f(*chain_args[0], **chain_args[1])
                else:
        	        # 戻り値がタプルのときは展開
                    chain_args = f(*chain_args)
            else:
                chain_args = f(chain_args)
        return chain_args
    
    # f * g
    def __mul__(self, other):
        if isinstance(other, Chain):
            return Chain(other.function + self.function)
        if isinstance(other, Callable):
            return Chain([other] + self.function)
        raise ValueError("uncallable object can't be chained.")
    
    # f >> g
    def __rshift__(self, other):
        if isinstance(other, Chain):
            return Chain(self.function + other.function)
        if isinstance(other, Callable):
            return Chain(self.function + [other])
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