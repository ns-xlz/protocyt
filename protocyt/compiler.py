# standart
from collections import deque
from lib2to3.pytree import Leaf
from lib2to3.pgen2 import token
from textwrap import dedent
# internal
from . import classes

def itail(iterable, size=1):
    'Yields `size` elements of iterable and iterator over rest of elements'
    iterator = iter(iterable)
    for _ in xrange(size):
        yield iterator.next()
    yield iterator

class TreeVisitor(object):
    '''
    Generic 2to3 AST-visitor
    '''
    def __init__(self, grammar):
        self.grammar = grammar
        self.types = set()

    def visit(self, *tree):
        'Abstract routing method. Executes methods depending of ast-node-type'
        queue = deque(tree)
        while queue:
            node = queue.popleft()
            if node.type in self.grammar.number2symbol:
                node_type = self.grammar.number2symbol[node.type]
            elif node.type in token.tok_name:
                node_type = token.tok_name[node.type]
            else:
                node_type = 'unknown'
            self.types.add(node_type)
            method = getattr(self, 'on_' + node_type, None)
            if method is not None:
                for part in method(node):
                    yield part
            else:
                queue.extend(node.children)

class CoreGenerator(TreeVisitor):
    '''
    Visitor over AST which converts nodes into instances structure.
    '''
    def on_NUMBER(self, node):
        yield node.value

    def on_indent(self, node):
        yield node.children[0].value

    on_label = on_indent

    def on_type(self, node):
        '''
        type: ( "double" | "float" | "int32" | "int64" | "uint32" | "uint64"
            | "sint32" | "sint64" | "fixed32" | "fixed64" | "sfixed32"
            | "sfixed64" | "bool" | "string" | "bytes" | userType )
        '''
        if isinstance(node.children[0], Leaf):
            yield node.children[0].value
        else:
            for child in self.visit(*node.children):
                yield child

    def on_package(self, node):
        '''
        package: "package" indent ( "." indent )* ";"
        '''
        name, = self.visit(*node.children)
        yield classes.Property(package_name=name)

    def on_fieldTail(self, node):
        '''
        fieldTail: type indent "=" NUMBER [ "[" fieldOption ( "," fieldOption )* "]" ] ";"
        '''
        type, name, index, options = itail(self.visit(*node.children), 3)
        yield classes.Field(index, name, type)

    def on_extension(self, node):
        '''
        extension: NUMBER [ "to" ( NUMBER | "max" ) ]
        '''
        if len(node.children) == 1:
            yield classes.Extension(node.children[0].value)
        elif len(node.children) == 3:
            yield classes.Extension(
                node.children[0].value,
                node.children[2].value)
        else:
            raise SyntaxError('Invalid extension')

    def on_groupOrField(self, node):
        '''
        groupOrField: label (groupTail | fieldTail)
        groupTail: "group" indent "=" NUMBER messageBody
        '''
        label, child = self.visit(*node.children)
        child.kind = label
        yield child

    def on_option(self, node):
        '''
        option: "option" optionBody ";"
        optionBody: indent ( "." indent )* "=" constant
        '''
        return
        yield

    def on_enum(self, node):
        '''
        enum: "enum" indent "{" ( option | enumField | ";" )* "}"
        '''
        name, _ = itail(self.visit(*node.children))
        yield classes.Enum(name)

    def on_message(self, node):
        '''
        message: "message" indent messageBody
        messageBody: "{" ( enum | message | extend | extensions | groupOrField | option | ";" )* "}"
        '''
        name, children = itail(self.visit(*node.children))
        code = dedent(str(node).strip().replace('#//', '//'))
        message = classes.Message(name, code)
        for child in children:
            child.set(message)
        yield message

    def on_userType(self, node):
        '''
        userType: ["."] indent ( "." indent )*
        '''
        yield '_'.join(self.visit(*node.children))

    def on_rpc(self, node):
        '''
        rpc: "rpc" indent "(" userType ")" "returns" "(" userType ")" ";"
        '''
        name, input_type, output_type = self.visit(*node.children)
        yield classes.RPC(name, input_type, output_type)

    def on_service(self, node):
        '''
        service: "service" indent "{" ( option | rpc | ";" )* "}"
        '''
        name, children = itail(self.visit(*node.children))
        service = classes.Service(name)
        for child in children:
            child.set(service)
        yield service

    def on_file_input(self, node):
        '''
        file_input: ( NEWLINE | message | extend | enum | import | package | option | service | ";" )* ENDMARKER
        '''
        protocol = classes.Protocol()
        for child in self.visit(*node.children):
            child.set(protocol)
        yield protocol
