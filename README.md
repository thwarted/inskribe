# Inskribe

Simple python templating library based on string.Formatter.

Inskribe's goals:

* focus on making formatting data unserialized from JSON easy
* recognize that, at its core, templating is string manipulation, transforming strings and inserting strings inside other strings
* be familiar by working like other common python templating idioms
* any logic/conditions should be written in python, not in some new-fangled templating language (that I'd have to write a parser for)
* despite that it's python code, don't require a lot of boilerplate code in the simpler, common cases

## Sample

Super simple sample that does not flaunt all the features, but shows the basic structure:

    import Inskribe

    class ShoppingList(Inskribe.Template):
        """
    {listkind} List:
    {items|GroceryItemList}
    """

    class GroceryItemList(Inskribe.ListTemplate):
        """  {#:02d}. {name}
    """

    itemstobuy = [{'name': 'carrots'},
                  {'name': 'celery'},
                  {'name': 'potatoes'},
                  {'name': 'milk'},
                  {'name': 'eggs'},
                  {'name': 'cheese'}]

    print ShoppingList(listkind="Shopping", items=itemstobuy)


## Usage

Templates are objects that can either be described literally in the code by subclassing Inskribe.Template or by instantiating Inskribe.Template directly.

The objects thus created will be templated when converted to strings.

Given this class definition:

    class MyTemplate(Inskribe.Template):
        """Hello, {who}!\n"""

then

    tplt = MyTemplate(who="World")

is equivalent to this:

    tplt = MyTemplate({'who':"World"})

is equivalent to this:

    tplt = Inskribe.Template(t="Hello, {who}!\n", item={'who':'World'})
    # this doesn't use the above defined class at all

So far, this works *exactly* like `string.Formatter`, which you may already be familiar with.

But you can also "filter" values passed to the template through other templates, using the pipe character, just like in UNIX.

    class Compliment(Inskribe.Template):
        """{0}, you look marvelous"""

    class MyTemplate(Inskribe.Template):
        """Hello, {who|Compliment}!\n"""

In this case, the value of `who` is passed to the `Compliment` template, and is accessible via the `{0}` expansion.  If the value that was passed in was an object or a dict, the attributes or elements would be accessible via the `string.Formatter` syntax `a.b.c.d` or `a[b][c]`, as deeply as the object nesting goes.  This is as `string.Formatter` works.

More than just classes can be used as filters.  You can also use functions as filters:

    def Compliment(s):
        return str(s) + ", you look marvelous"

    class MyTemplate(Inskribe.Template):
        """Hello, {who|Compliment}!\n"""

This works exactly the same as the `Compliment` filter being defined as a subclass of Inskribe.Template because object instantiation and function calling are syntaxically similar in python.  As long as the instantiated object or the function return a string (or something that can be converted/serialized to a string), it will work.

Anything in the module or class scope should be accessible as a filter:

    import string

    class MyTemplate(Inskribe.Template):
        """Hello, {who|capsit}!\n"""

        @staticmethod
        def capsit(s):
            return string.capitalize(s)

In this example, `capsit` could also be defined in the module's, instead of the class's, scope.

If you want to hide a module or class attribute from being accessible to the template, prefix the name with an underscore.

But why bother implementing a fleet of tiddlywink little wrappers for all those kinds of things?  Since the `string` module is visible in the module scope above, this will work too:

    import string

    class MyTemplate(Inskribe.Template):
        """Hello, {who|string.capitalize}!\n"""

Filters can be chained, just like UNIX pipes, the output of ones to the left feeding into the inputs to the right.

    import string

    class MyTemplate(Inskribe.Template):
        """Hello, {who|string.capitalize|string.swapcase}!\n"""

You can also parameterize these functions.  Let's leverage the `time` module to format UNIX timestamp values in the template as something human readable:

    import time

    class MyTemplate(Inskribe.Template):
        """The date of record is
        {recordedat|int|time.gmtime|time.strftime(%Y-%m-%d %T)}
        """

    print MyTemplate(recordedat="1262332800")
    => '2010-01-01 08:00:00'

This will filter the value of `recordedat` through `int()`, then `time.gmtime`,
then through `time.strftime`, passing the string `"%Y-%m-%d %T"` as the first 
argument and the value of `recordedat` for the second argument.

This will only work with functions that take two arguments, the first being a string, and the second of which is the value being filtered through it.  For more complex argument passing, define a function and don't specify the arguments in the template.

So far, we've been using the docstrings for the classes to store the template.  This makes the common case easy to specify.  If you want to arrange the class definition differently to make it more obvious, assign the template to the class variable `t`:

    class MyTemplate(Inskribe.Template):
        t = "This is the template string."

There are two other class variables that go into the generated output of the template, `pre` and `post`, which come in handy for formatting HTML lists, or if you otherwise just want to split the template up into parts for documentation purposes.  (we'll get to `Inskribe.ListTemplate` class in a moment):

    class MyHTMLList(Inskribe.ListTemplate):
        pre = "<ul>"
        t = "<li>{name}</li>"
        post = "</ul>"

The value of `pre` will be preprended to the output and the value of `post` will be appended.

It may be helpful to define "constants" in one place in the class or module to make the template maintenance easier:

    class_ = "urgent"

    class MyUrgentSpan(Inskribe.Template):
        style = "color: red;"
        t = """<span class="{class_}" style="{style}">{0}</span>"""

The values passed into the template override attributes defined on the module or class, so to access class attributes unambiguously, you could use `{module.class_}` or `{self.style}` in the above template.

Since there is no support for conditionals or loops in the template string itself, any customization of the template should be done in a method named `setup`:

    class MyTemplate(Inskribe.Template):
        """Hello, {who}{punct}"""

        punct = "."
        def setup(self):
            if self._kwargs['who'] == "George Oscar Bluth":
                self._kwargs['who'] = 'GOB' # prefers nickname

            if "excited" in self._kwargs:
                self.punct = '!'

The object itself and the values of `self._kwargs`and `self._args` can be modified in the `setup` method, and changes will be seen by the template.  I don't recommend making a habit of modifying the values passed into the template, but rather use this to change values in object attributes based on the incoming values.

Remember that anything that can be converted to a string can be put into a template, even another template.  Say you have two ways to format the data based on some value in it.  You can instantiate other templates and assign them to object attributes:

    class MyTemplate(Inskrike.Template):
        """{greeting}

        Your account info:
         ...
        """

        def setup(self):
            if self._kwargs['verison'] == '1':
                self.greeting = Inskribe.Template(
                       t="""Hello, {name|string.captialize}.""", 
                    item=self._kwargs)
            else
                self.greeting = Inskribe.Template(
                       t="""Welcome, {username}!""",
                    item=self._kwargs)

The `Inskribe.ListTemplate` can be used to itteratively apply a list of dicts to the same template.  Using the HTML unordered list example from above:

    class MyHTMLList(Inskribe.ListTemplate):
        pre = "<ul>\n"
        t = "<li>{name}</li>\n"
        post = "</ul>"

    print MyHTMLList(items=['itemA', 'itemB', 'itemC'])

will expand to:

    <ul>
    <li>itemA</li>
    <li>itemB</li>
    <li>itemC</li>
    </ul>

`Inskribe.ListTemplate` provides a special expansion, `{#}` that will be assigned the results of the generator in `self._sequence_labeler` as each element of the list is expanded.  This can be used to control things like line numbering, or cycle through HTML element classes to create alternating colored table rows, etc. There are three sample sequence labelers defined in `Inskribe.Labelers`: `simple_numbers`, `cycle`, and `pairs`.  The `self._sequence_labeler` attribute can be assigned in the `setup` method:

    class MyHTMLList(Inskribe.ListTemplate):
        pre = "<ul>\n"
        t = "<li class="{#}">{name}</li>\n"
        post = "</ul>"

        def setup(self):
            rowhighlight = ('odd', 'even')
            self._sequence_labeler = Inskribe.Labelers.cycle(rowhighlight)

    print MyHTMLList(items=['itemA', 'itemB', 'itemC'])

Usually, the sequence labeler generator will return strings or numbers, but it can return a dict, list or object also, and using regular `string.Formatter` syntax, off the value `#` in the template , like `{#[field]}`, the different keys or attributes can be accessed to have complex sequences.  The `Inskribe.Labelers.pairs` method is an example of that, returning both a count and a cycling value for each iteration.

Because this is based on `string.Formatter`, you can also use "format specifications" as they are defined for `string.Formatter`, to format floats and integers.

    class GroceryItemList(Inskribe.ListTemplate):
        """  {#:02d}. {name}
    """

The `{#:02d}` formats the sequence label as a two digit integer with a leading
zero.

## Notes

I really wanted to implement this by overloading the conversion field that `string.Formatter` allows (after a `!`). By default it provides a minimal number of conversions, including string and repr, designated by `s` and `r`.  `string.Formatter` provides hooking into the conversion by calling `convert_field`.

Unfortunately, the base `string.Formatter.parse` function is implemented in C and is hardcoded to accept only one character for the conversion field.  A wide range of characters can be used, letters, numbers and much puncutation, and they get passed to the `convert_field` method, but single characters are not very very self documenting and kind of limited.  I consider this one character limitation of the conversion string to be a serious oversight in the implementation of `string.Formatter.parse`.

But `string.Formatter` can be subclassed, and the parse function can be overridden.  But it's written in C for a reason: to be fast.  So I let the C code do its job and then examine the value strings looking for pipes and overriding the

Ultimately, I like this better because the use of the pipe character is already familiar in relation to filtering.  But it would have been nice to be able to leverage the documented template syntax and just provide a way to access conversion methods directly by name.
