# This file was found from a 3rd party
# https://bitbucket.org/thesheep/iscconf/

import ply.lex
import ply.yacc


tokens = (
    "NAME",
    "IPADDR",
    "DOMAIN",
    "MACADDR",
    "BRACE_OPEN",
    "BRACE_CLOSE",
    "SEMICOLON",
    "COMMA",
    "STRING",
    "INTEGER",
    "CIDR4",
)


t_ignore = " \t"
# Added ! for support of allow-query { !key external; };
t_NAME = r"[a-zA-Z!][a-zA-Z0-9-]*[a-zA-Z0-9]*"
t_IPADDR = r"([0-2]?[0-9]?[0-9][.]){3}[0-2]?[0-9]?[0-9]"
t_DOMAIN = r"([a-z][a-z0-9-]*[.])+[a-z][a-z0-9-]*[.]?"
t_BRACE_OPEN = r"{"
t_BRACE_CLOSE = r"}"
t_SEMICOLON = ";"
t_COMMA = ","
t_CIDR4 = r"([0-2]?[0-9]?[0-9][.]){3}[0-2]?[0-9]?[0-9]/[0-3]?[0-9]"
t_ignore_COMMENT = r"[#][^\n]*"


class Error(Exception):
    pass


class SyntaxError(Error):
    pass


class LexicalError(Error):
    pass


def t_MACADDR(t):
    r"([0-9a-fA-F][0-9a-fA-F]:){5}[0-9a-fA-F][0-9a-fA-F]"
    t.value = t.value.lower()
    return t


def t_INTEGER(t):
    r"-?[0-9]+(?![a-fA-F0-9:.])"  # Avoid conflicts with MAC and IP addresses
    t.value = int(t.value)
    return t


def t_STRING(t):
    r'"([^"]|\\")*"'
    t.value = t.value[1:-1]
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    raise LexicalError("Lexical error at %r line %d" % (t.value, t.lineno))


def p_content_empty(p):
    r"content :"
    p[0] = {}


def p_content(p):
    r"content : content entry"
    p[0] = dict(p[1])
    p[0].update(p[2])


def p_value(p):
    r"""
    value : IPADDR
          | DOMAIN
          | MACADDR
          | STRING
          | INTEGER
          | NAME
          | CIDR4
    """
    p[0] = p[1]


def p_value_list_start(p):
    r"""value_list : value COMMA value"""
    p[0] = [p[1], p[3]]


def p_value_list(p):
    r"""value_list : value_list COMMA value"""
    p[0] = p[1] + [p[3]]


def p_key_part(p):
    r"""
    key_part : NAME
             | DOMAIN
             | IPADDR
             | MACADDR
             | STRING
             | INTEGER
             | CIDR4
    """
    p[0] = p[1]


def p_key_single(p):
    r"key : key_part"
    p[0] = (p[1],)


def p_key(p):
    r"key : key key_part"
    p[0] = p[1] + (p[2],)


def p_entry(p):
    r"""
    entry : key value SEMICOLON
          | key value_list SEMICOLON
          | key block
          | key block SEMICOLON
    """
    p[0] = {p[1]: p[2]}


def p_entry_nokey(p):
    r"""
    entry : value SEMICOLON
    """
    p[0] = {(): p[1]}


def p_block(p):
    r"block : BRACE_OPEN content BRACE_CLOSE"
    p[0] = p[2]


def p_error(p):
    if p:
        raise SyntaxError("Syntax error at %r line %d" % (p.value, p.lineno))
    else:
        raise SyntaxError("Syntax error")


def parse(string):
    return ply.yacc.parse(string)


ply.lex.lex(debug=0)
ply.yacc.yacc(debug=0)
