import warnings

class Chain:
    def __init__(self, function):
        if isinstance(function, list):
            self.function = function
        else:
            self.function = [function]
    
    def __call__(self, *args, **kwargs):
        f_idx = 0
        
        def none2tuple(x):
            if x is None:
                warnings.warn(f"Chain broken with 'None' value between '{self.function[f_idx-1].__name__}' and '{self.function[f_idx].__name__}'", RuntimeWarning)
                return ()
            return x
        
        chain_args = self.function[0](*args, **kwargs)
        for f_idx, f in enumerate(self.function[1:], 1):
            chain_args = f(*none2tuple(chain_args))
        return chain_args
    
    def __rshift__(self, other):
        return Chain(self.function + other.function)

def chain(function):
    return Chain(function)
    
@chain
def fuga(x, y, z):
    return 3 * x, y, z

@chain
def piyo(x, y, z):
    return x, y + 1, z

fp = fuga >> piyo
fp(1, 2, 3)
