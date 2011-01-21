# vim: fileencoding=utf-8:ai:ts=4:expandtab

import string
import re
import sys


def unicodify(s):
    if isinstance(s, unicode):
        return s
    if isinstance(s, str):
        for decodeargs in (('utf-8',), ('iso-8859-2',), ('ascii', 'replace')):
            try:
                return s.decode(*decodeargs)
            except UnicodeError, e:
                pass
    return s

# serializing Template objects should always return unicode objects
# which the caller need to encode in a chosen encoding to actually
# output

class Template(object):
    pre = u''  # static string that will prefix the template output
    t = u''    # the template itself
    post = u'' # static string that will be appended to the template output

    class Formatter(string.Formatter):
        # matches things like time.strftime(%Y)
        funcargsre = re.compile(r'^([^(]+)(?:\((.+)\))?$')
        ctx = {} # context that we'll search for filters in

        def __init__(self, ctx):
            self.ctx = ctx

        def parse(self, format_string):
            r = super(Template.Formatter, self).parse(format_string)
            for literal_text, field_name, format_spec, conversion in r:
                if field_name is not None:
                    filters = field_name.split("|")
                    field_name = filters.pop(0)
                    if filters:
                        conversion = tuple(filters)
                yield (literal_text, field_name, format_spec, conversion)

        simplefilters = {
            "int": lambda x: int(x),
            "float": lambda x: float(x),
            "str": lambda x: str(x),
            "repr": lambda x: repr(x),
        }

        def convert_field(self, value, conversion):
            if isinstance(conversion, tuple):
                # if it's a tuple, it's the output of the above parse function
                for filter in conversion:
                    if not filter:
                        continue # FIXME, value|| should be a fatal error
                    if filter in self.simplefilters:
                        value = self.simplefilters[filter](value)
                        continue

                    sre = self.funcargsre.match(filter)
                    filter, handlerarg = sre.groups()
                    try:
                        handler = self.get_field(filter, [], self.ctx)
                    except AttributeError as e:
                        msg = e.args[0]
                        msg += " when evaluating template %r (module %s)" % (self.__name__, self.__module__)
                        raise AttributeError(msg)
                    else:
                        handler, ctxname = handler
                        a = []
                        if handlerarg:
                            a.append(handlerarg)
                        a.append(value)
                        value = handler(*a)

                return value
            else:
                return super(Template.Formatter, self).convert_field(value, conversion)

    _args = []
    _kwargs = {}
    _formatter = None
    _result = False
    def __init__(self, *args, **kwargs):
        # when passed a single argument, it must be either a list or a
        # dict (and if it's a list, should be using ListTemplate instead)
        # otherwise, keyword arguments become the expected dict
        #  takes:
        #    - a single dict => self._kwargs = that dict
        #    - a single list => self._args = that list
        #    - a single anything => self._args = [a] (so it's accessible with {0} index expansion)
        #    - a empty args, non-empty kwargs =>self._kwargs = kwargs
        #    - anything else => self._args, self._kwargs = args, kwargs
        #    - t = template str, item=dict => self._kwargs=item, self._args=[]
        #    - t = template str, items=list => self._kwargs={}, self._args=items
        if not kwargs:
            if len(args) == 1:
                if type(args[0]) == dict:
                    self._args = [args[0]] # entire value accessible as {0}
                    self._kwargs = args[0] # elements of value accessible as {element}
                elif type(args[0]) == list:
                    # TODO warn? should be using ListTemplate instead?
                    self._args = args[0]
                    self._kwargs = {}
                else:
                    # convert anything else into a single element list
                    # which will be accessible via {0}
                    self._args = [args[0]]
                    self._kwargs = {}
            else:
                # nothing passed in, template better not need any expansions
                self._args = []
                self._kwargs = {}
        else:
            if not args:
                if len(kwargs) == 2 and 't' in kwargs and 'item' in kwargs:
                    self.t = kwargs['t']
                    if self.__class__ == Template:
                        self._args = []
                        self._kwargs = kwargs['item']
                    elif self.__class__ == ListTemplate:
                        # FIXME this logic should be in ListTemplate
                        self._args = kwargs['items']
                        self._kwargs = {}
                else:
                    self._args = []
                    self._kwargs = kwargs
            else:
                self._args = args
                self._kwargs = kwargs

        if not self.t and self.__doc__:
            self.t = self.__doc__

        self.t = unicodify(self.t)
        self.pre = unicodify(self.pre)
        self.post = unicodify(self.post)

        self.setup()
        ctx = self._find_context()
        self._kwargs = dict(ctx, **self._kwargs)

        self._formatter = self.Formatter(ctx)

    def setup(self):
        pass

    def _find_context(self):
        """Builds up a context for searching for filters by adding the
        attributes of the module the object is defined in and the
        object itself.

        Anything that starts with an underscore or is named pre, t, or post
        is skipped.
        """
        trycontexts = (sys.modules[self.__module__], self)
        isprivate = lambda x: False if x.startswith('_') or x in ('pre', 't', 'post') else True
        context = {}
        for ctx in trycontexts:
            for k in filter(isprivate, dir(ctx)):
                context[k] = getattr(ctx, k)
        # FIXME: these are less than ideal names, it's possible the template
        # values use these keys
        context['self'] = self
        context['module'] = sys.modules[self.__module__]
        return context

    # string.Formatter appears to be a maze of twisty passages
    #
    # .vformat needs to convert everything to a basestring-compatible format
    # in order to actually concatentate all the parts into a single output
    # it does this by calling
    #  - string.Formatter.format_field(.., value, fs)
    #  - which calls format(value, fs)
    #  - which calls value.__format__(fs)
    # since we use string.Formatter in render the template, subtemplates will
    # have their own __format__ method called to be character-ized, and this
    # then invokes stringifcation which attempts convering to the default
    # charset, ascii, which causes encoding issues because we really should be
    # utf8 everywhere in here.
    # 
    # consider: might be better done by overriding string.Formatter.format_field
    #           above in Template.Formatter to not just blindly call format()
    #           which ultimately calls this __format__ method.  We'd still
    #           need to render the template though.
    #
    # all three, __format__, __unicode__ and __str__ are used in various places
    # of string.Formatter to serialize objects to character streams, so we need
    # define all three, and they all pretty much do the same thing.
    def __format__(self, format_spec):
        if self._result:
            return self._result
        o = unicodify(self._formatter.vformat(self.t, self._args, self._kwargs))
        return format(o, format_spec)

    def __unicode__(self):
        self._result = self.__format__('')
        return self._result

    def __str__(self):
        return self.__unicode__()


# ListTemplate differs from Template in how a list is interpreted when passed
# in as the first arg.  ListTemplate will iterate over the elements, whereas
# Template will expose them as positional expansions {0}, {1}, etc
class ListTemplate(Template):
    _sequence_labeler = None # need some interface to set this
    def __init__(self, *args, **kwargs):
        self._sequence_labeler = Labelers.simple_numbers()
        super(ListTemplate, self).__init__(*args, **kwargs)

    def __format__(self, format_spec):
        if self._result:
            return self._result
        o = u''
        # FIXME support iterators/generators in general here, rather than just list instances
        if isinstance(self._args, list) and len(self._args) > 0:
            c = 0
            for item in self._args:
                item['_'] = item
                item['#'] = self._sequence_labeler.next() if self._sequence_labeler else '#'
                # we don't merge in self._kwargs here, the item overrides it
                x = unicodify(self._formatter.vformat(self.t, self._args, item))
                o += format(x, format_spec)
                del item['_'] # break circular reference
        return self.pre + o + self.post



class Labelers(object):
    @staticmethod
    def simple_numbers(start=0):
        while True:
            start += 1
            yield start

    @staticmethod
    def cycle(cycle=None):
        cycle = cycle or ('black', 'white')
        count = 0
        while True:
            count += 1
            yield cycle[count % len(cycle)]

    @staticmethod
    def pairs(cycle=None):
        cycle = cycle or ['black', 'white']
        count = 0
        while True:
            count += 1
            yield {'num': count, 'color':cycle[count % len(cycle)]}

