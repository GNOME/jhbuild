
# add True and False constants, for the benefit of Python < 2.2.1
import __builtin__
if not hasattr(__builtin__, 'True'):
    __builtin__.True = (1 == 1)
    __builtin__.False = (1 != 1)
del __builtin__
