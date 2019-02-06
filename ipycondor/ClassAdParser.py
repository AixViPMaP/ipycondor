# Copyright 2019 Mingxuan Lin

from __future__ import print_function
from six import string_types
import copy, re
import classad

def _naturalsize(value, scale=1):
    try:
        from humanize import naturalsize
        return naturalsize(scale*value, binary=True)
    except Exception:
        return value

def rule(x, plain=False):
    """
    Decorater for class method of a BaseParser subclass
    Used together with BaseParser.meta

    Usage:
        @rule  |  @rule(r'\\w*Date')  | @rule('My keyword', plain=True)
        def rulename(value, key, classad_object):
            return value

    """
    pt = None
    if isinstance(x, string_types):
        if plain:
            pt = x
        else:
            pt = re.compile(x, flags=re.IGNORECASE)

    def decorater(f):
        f._meta_type = "parser_rule"
        f.pattern     = pt if pt else f.__name__
        return f

    return decorater(x) if callable(x) else decorater


class BaseParser(object):
    """
    Sample usage:
        @BaseParser.meta
        class ClassAdParser(BaseParser):
            # This is a simple rule which will match the attribute name `JobStatus`
            @rule
            def JobStatus(v):
                lookuptable=['Idle','Running','Removed','Completed','Held','Transferring Output']
                return lookuptable[v-1]
        p = ClassAdParser()
        p.parse(jobClassAd, 'JobStatus')
    """
    __simple_rules = {}
    __re_rules = tuple()
    @staticmethod
    def meta(cls):
        cls.__simple_rules = {}
        cls.__re_rules = []
        for n in dir(cls):
            if n.startswith('_'): continue
            func = getattr(cls, n)
            if getattr(func, '_meta_type',None) != "parser_rule": continue
            pattern = getattr(func, 'pattern', None)
            if isinstance(pattern, string_types):
                cls.__simple_rules[pattern.lower()]=func
            else:
                cls.__re_rules.append([pattern, func])
        return cls

    def parse(self, clsad, key):
        """
        Parse the value of the named attribute of a ClassAd object `clsad[key]`.

        :param clsad: the ClassAd object to be parsed
        :type  clsad: ClassAd
        :param key: name of the attribute
        :type  key: string
        :rtype: string
        """
        value = copy.deepcopy(clsad.get(key, None))
        srule=self.__simple_rules.get(key.lower(), None)
        if srule:
            value = _safe_call( srule, value , key , clsad)
            if value: return value
        for pt, srule in self.__re_rules:
            if pt.match(key):
                value = _safe_call( srule, value , key , clsad)
                if value: return value
        # No match
        if type(value).__module__ == 'classad':
            value = str(value)
        return value

def _safe_call(f, *args):
    import inspect
    n = len(inspect.getargspec(f)[0])
    args = args[:n]
    try:
        return f(*args)
    except Exception as err:
        return str(err)

@BaseParser.meta
class QueryParser(BaseParser):
    """
    Parser class for the ClassAd objects returned by `schedd.query`
    """
    @rule
    def JobUniverse(value):
        Universes={1:'standard', 5:'vanilla', 7:'scheduler', 8:'MPI', 9:'grid', 10:'java', 11:'parallel', 12:'local', 13:'vm'}
        return Universes.get(value, 'unknown')

    @rule
    def JobStatus(value, k, clsad):
        S=['Idle','Running','Removed','Completed','Held','Transferring Output','Suspended']
        return S[value-1]

    @rule
    def DiskUsage(value):
        return '{0} KB'.format(value)

    @rule(r'\w*(Date|Expiration|ServerTime|LastMatchTime)$')
    def timestamp2date(value):
        import datetime
        if isinstance(value, int) and value > 0:
            return datetime.datetime.fromtimestamp(value)
        else:
            return None

    @rule
    def RemoteHost(value, k, clsad):
        return value if value else clsad.get('LastRemoteHost','')

    @rule
    def JobId(value, key, classad):
        return classad.get('GlobalJobId', '').split('#')[1]

    @rule
    def ExitStatus(value, key, classad):
        if classad.get('CompletionDate','') > 0:
            return value
        else:
            return None

    @rule(r'\w*(Memory)$')
    def mbyte2human(value):
        return _naturalsize(value, 1024*1024 )

    @rule(r'\w*(Disk)$')
    def kbyte2human(value):
        return _naturalsize(value, 1024 )
