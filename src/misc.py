from ast_tools import *
from typing import List
from parser import Parser
from lexer import Lexer

def process(source):
    '''parse the source text here. you may return the AST specified in ast_tools.py or something else.'''
    parser = Parser()
    lexer = Lexer()
    return parser.parse(lexer.tokenize(text=source))

def generate_ast(intermediate) -> Program:
    '''return the AST using the output of process() here.'''
    return intermediate

def undeclared_vars(intermediate) -> List[Identifier]:
    '''return all of the undeclared uses of the variables in the order they appear in the source code here, using the return value of process()'''
    return SemanticVisitor().visit(intermediate)[0]

def multiple_var_declarations(intermediate) -> List[Identifier]:
    '''return all of the subsequent declarations of a previously declared variable if the re-declaration cannot be explained by shadowing,
    in the order they appear in the source code, using the return value of process()'''
    return SemanticVisitor().visit(intermediate)[1]
