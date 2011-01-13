
import string
import re
import sys

class Template(object):
    pre = ''  # static string that will prefix the template output
    t = ''    # the template itself
    post = '' # static string that will be appended to the template output

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
    def __init__(self, *args, **kwargs):
        # when passed a single argument, it must be either a list or a
        # dict (and if it's a list, should be using ListTemplate instead)
        # otherwise, keyword arguments become the expected dict
        #  takes:
        #    - a single dict => self.kwargs = that dict
        #    - a single list => self.args = that list
        #    - a empty args, non-empty kwargs =>self.kwargs = kwargs
        #    - anything else => self.args, self.kwargs = args, kwargs
        #    - t = template str, item=dict => self.kwargs=item, self.args=[]
        #    - t = template str, items=list => self.kwargs={}, self.args=items
        if not kwargs:
            if len(args) == 1:
                if type(args[0]) == dict:
                    self._args = []
                    self._kwargs = args[0]
                elif type(args[0]) == list:
                    # TODO warn? should be using ListTemplate instead?
                    self._args = args[0]
                    self._kwargs = {}
                else:
                    raise TypeError("single argument to %s constructor must be either list or dict" % (self.__class__,))
            else:
                raise TypeError("%s constructor takes either a single list or single dict without keyword arguments" % (self.__class__,))
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

        self._formatter = self.Formatter(self._find_context())

    def _find_context(self, frameindex=1):
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
        context['self'] = self
        return context


    def __str__(self):
        o = self._formatter.vformat(self.t, self._args, self._kwargs)
        return str(self.pre) + o + str(self.post)


class ListTemplate(Template):
    _sequence_labeler = None # need some interface to set this
    def __init__(self, *args, **kwargs):
        super(ListTemplate, self).__init__(*args, **kwargs)
        self._sequence_labeler = Labelers.simple_numbers()

    def __str__(self):
        o = ''
        # FIXME support iterators/generators in general here, rather than just list instances
        if isinstance(self._args, list) and len(self._args) > 0:
            c = 0
            for item in self._args:
                item['#'] = self._sequence_labeler.next() if self._sequence_labeler else '#'
                # we don't merge in self._kwargs here, the item overrides it
                o += self._formatter.vformat(self.t, self._args, item)
        return str(self.pre) + o + str(self.post)


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

