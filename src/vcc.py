#!/usr/bin/env python3

# Vox compiler
# Named vcc to make it sound familiar.

# vcc.py adapted from tester.py

import argparse
import asm
from misc import *

arg_parser = argparse.ArgumentParser()

arg_parser.add_argument('filename', type=str)
arg_parser.add_argument('--parse', action='store_true')

args = arg_parser.parse_args()

with open(args.filename,'r') as f:
    source = f.read()

    if args.parse:
        intermediate = process(source)
        ast = generate_ast(intermediate)
        print('PrintVisitor Output:')
        print(PrintVisitor().visit(ast))
        undecl_vars = undeclared_vars(intermediate)
        multiple_decls = multiple_var_declarations(intermediate)
        result = 'Undeclared vars:\n'
        result = result + '\n'.join([str(iden) for iden in undecl_vars])
        result = result + '\n'+'Multiple var declarations:\n'
        result = result + '\n'.join([str(iden) for iden in multiple_decls])
        print(result)

    else:
        intermediate = process(source)
        ast = generate_ast(intermediate)

        asm.AsmGenerator().compile(ast)