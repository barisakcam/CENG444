from ast_tools import *

# Optimization TODOs:
# For artihmetic, if both args immediate, calculate in python
# if t0 stores and loads consecutevely remove instructions.
# DID NOT DO THE OPTIMIZATIONS YET

class ActivationRecord:
    def __init__(self) -> None:
        self._frame_v_start = 24
        self._frame_size = 16 # 16 byte reserved
        self._block = CodeBlock(None)

class CodeBlock:
    _global_data = {}

    def __init__(self, parent) -> None:
        self.parent = parent
        self.children = []
        self.vars = {}

    def __repr__(self) -> str:
        if len(self.children) > 0:
            return f'{self.vars}{self.children}'
        else:
            return f'{self.vars}'

    def addGlobal(self, var, addr) -> None:
        #self._global_data[var] = "".join(['.',var])
        self._global_data[var] = addr

    def addVariable(self, var, addr) -> None:
        self.vars[var] = addr

    def addChild(self, block) -> None:
        block.parent = self
        self.children.append(block)

    def getVariable(self, var):
        if var in self.vars:
            return self.vars[var]
        else:
            if isinstance(var, bool):
                return (float(var), 1)
            elif isinstance(var, float) or isinstance(var, int):
                return (float(var), 1) # TODO: CHECK FLOAT
            elif self.parent is not None:
                return self.parent.getVariable(var)
            elif var in self._global_data:
                return self._global_data[var]
            else:
                return (var, -1) #Maybe undeclared variable 

class TACInstruction:
    def __init__(self, op, arg1, arg2, result, block):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.result = result
        self.block = block

    def print(self):
        if self.op == None:
            print(f'{self.result}')
        elif self.op == '=':
            print(f'{self.result} = {self.arg1}')
        elif self.op == 'AUMINUS' or self.op == '!':
            print(f'{self.result} = {self.op} {self.arg1}')
        elif self.op == "PRINT":
            print(f'PRINT {self.arg1}')
        else:
            print(f'{self.result} = {self.arg1} {self.op} {self.arg2}')

class AsmGenerator(ASTNodeVisitor):
    def __init__(self):
        ASTNodeVisitor.__init__(self)
        self.asm_list = []
        self.tac_list = []
        self._frame_pos = 0
        self._last_temp = -1
        self._frame_v_start = 24
        self._frame_size = 16 # 16 byte reserved
        self._variable_tbl = {}
        self._variable_size = 0
        self._string_tbl = {}
        self._string_size = 0
        self._last_string = -1
        self._last_jump = - 1
        self._global_data = {}
        self._activation_tbl = {}
        self._current_block = CodeBlock(None)
        self._functions_done = set()
        self._functions_wait = set()
        self._functions = {}
        self._last_vec = -1
        self._return_label = None

        self._text = []
        self._data = []

    def generate_temp(self):
        self._last_temp += 1
        self._frame_size += 8
        return f'${self._last_temp}'

    def generate_string(self):
        self._last_string += 1
        return f'.S{self._last_string}'

    def generate_jump(self):
        self._last_jump += 1
        return f'.L{self._last_jump}'

    def generate_vector(self):
        self._last_vec += 1
        return f'.V{self._last_vec}'

    def visit_SLiteral(self, sliteral: SLiteral):
        temp = self.generate_string()
        self._current_block.addGlobal(temp, (temp, -1))
        self.tac_list.append(TACInstruction("GLOBAL_STR_DECL", sliteral.value, None, temp, self._current_block))

        return temp

    def visit_Program(self, program: Program):

        self._current_block = CodeBlock(None)
        self._frame_size = 16

        pos = len(self.tac_list)

        for elem in program.var_decls:
            self.add_global(elem)

        for elem in program.statements:
            self.visit(elem)

        self.tac_list.insert(pos, TACInstruction("STACKUP", self._frame_size, None, None, self._current_block))
        self.tac_list.append(TACInstruction("STACKDOWN", self._frame_size, None, None, self._current_block))

        while len(self._functions_wait) > 0:
            for elem in program.fun_decls:
                self.visit(elem)

        # Align frame 16-bytes
        while self._frame_size % 16 != 0:
            self._frame_size += 8

        return "program"

    def visit_ErrorStmt(self, errorstmt: ErrorStmt):
        return "errorstmt"

    def add_global(self, vardecl: VarDecl):

        if vardecl.initializer is None:
            self._current_block.addGlobal(vardecl.identifier.name, ("".join(['.', vardecl.identifier.name]), 1))
            self.tac_list.append(TACInstruction("GLOBAL_VAR_DECL", None, None, vardecl.identifier.name, self._current_block))
            return

        elif isinstance(vardecl.initializer, AExpr):
            self._current_block.addGlobal(vardecl.identifier.name, ("".join(['.', vardecl.identifier.name]), 1))
            self.tac_list.append(TACInstruction("GLOBAL_VAR_DECL", self.visit(vardecl.initializer), None, vardecl.identifier.name, self._current_block))
            return

        elif isinstance(vardecl.initializer, LExpr):
            self._current_block.addGlobal(vardecl.identifier.name, ("".join(['.', vardecl.identifier.name]), 1))
            self.tac_list.append(TACInstruction("GLOBAL_VAR_DECL", self.visit(vardecl.initializer), None, vardecl.identifier.name, self._current_block))
            return

        elif isinstance(vardecl.initializer, SLiteral):
            self._current_block.addGlobal(vardecl.identifier.name, ("".join(['.', vardecl.identifier.name]), -1))
            self.tac_list.append(TACInstruction("GLOBAL_STR_DECL", vardecl.initializer.value, None, vardecl.identifier.name, self._current_block))
            return

        elif isinstance(vardecl.initializer, List):
            self._current_block.addGlobal(vardecl.identifier.name, ("".join(['.', vardecl.identifier.name]), len(vardecl.initializer)))
            self.tac_list.append(TACInstruction("GLOBAL_VEC_DECL", [self.visit(elem) for elem in vardecl.initializer], None, vardecl.identifier.name, self._current_block))
            return

    def visit_VarDecl(self, vardecl: VarDecl):

        if vardecl.initializer is None:
            self._frame_size += 8
            self._current_block.addVariable(vardecl.identifier.name, (self._frame_size, 1))
            self.tac_list.append(TACInstruction(None, None, None, vardecl.identifier.name, self._current_block))
            return

        elif isinstance(vardecl.initializer, Expr):
            self._frame_size += 8
            self._current_block.addVariable(vardecl.identifier.name, (self._frame_size, 1))
            self.tac_list.append(TACInstruction('=', self.visit(vardecl.initializer), None, vardecl.identifier.name, self._current_block))
            return "init literal"

        elif isinstance(vardecl.initializer, List):
            self._frame_size += 8 * len(vardecl.initializer) + 8
            self._current_block.addVariable(vardecl.identifier.name, (self._frame_size, len(vardecl.initializer)))
            self.tac_list.append(TACInstruction('PUTADDRESS', vardecl.identifier.name, None, None, self._current_block))
            for i in range(len(vardecl.initializer)):
                self.tac_list.append(TACInstruction('SETVECTOR', vardecl.identifier.name, i, self.visit(vardecl.initializer[i]), self._current_block))

            return "init list"

        else:
            return "NOT IMPLEMENTED"

    def visit_FunDecl(self, fundecl: FunDecl):
        if fundecl.identifier.name in self._functions_wait:
            versions = self._functions[fundecl.identifier.name].copy()

            if len(versions) == 0:
                self._functions_wait.remove(fundecl.identifier.name)
                return

            for version in versions:
                self.tac_list.append(TACInstruction("LABEL", ''.join([fundecl.identifier.name, '.', version]), None, None, self._current_block))

                temp_block = self._current_block
                temp_frame = self._frame_size
                self._current_block = CodeBlock(None)
                self._frame_size = 16

                pos = len(self.tac_list)


                for i in range(0, len(version)):
                    self._frame_size += 8
                    self._current_block.addVariable(fundecl.params[i].name, (self._frame_size, int(version[i])))
                    self.tac_list.append(TACInstruction("GETPARAM", i, None, fundecl.params[i].name, self._current_block))

                self.visit(fundecl.body)

                self.tac_list.insert(pos, TACInstruction("STACKUP", self._frame_size, None, None, self._current_block))
                if self._return_label != None:
                    self.tac_list.append(TACInstruction("LABEL", self._return_label, None, None, self._current_block))
                    self._return_label = None
                self.tac_list.append(TACInstruction("STACKDOWN", self._frame_size, None, None, self._current_block))

                self._functions_done.add(''.join([fundecl.identifier.name, '.', version]))
                self._functions[fundecl.identifier.name].remove(version)
                self._current_block = temp_block
                self._frame_size = temp_frame

        else:
            return

        return "fundecl"

    def visit_Assign(self, assign: Assign):
        self.tac_list.append(TACInstruction('=', self.visit(assign.expr), None, assign.identifier.name, self._current_block))
        return assign.identifier.name

    def visit_SetVector(self, setvector: SetVector):
        if isinstance(setvector.vector_index, ALiteral):
            self.tac_list.append(TACInstruction('SETVECTOR', setvector.identifier.name, setvector.vector_index.value, self.visit(setvector.expr), self._current_block))
        else:
            self.tac_list.append(TACInstruction('SETVECTOR', setvector.identifier.name, self.visit(setvector.vector_index), self.visit(setvector.expr), self._current_block))
        return 0

    def visit_ForLoop(self, forloop: ForLoop):
        jump1 = self.generate_jump()
        self._current_block.addGlobal(jump1, (jump1, 0))
        jump2 = self.generate_jump()
        self._current_block.addGlobal(jump2, (jump2, 0))

        if forloop.initializer is not None:
            self.visit(forloop.initializer)
            
        self.tac_list.append(TACInstruction("LABEL", jump1, None, None, self._current_block))

        if forloop.condition is not None:
            temp = self.visit(forloop.condition)
        else:
            temp = 0

        self.tac_list.append(TACInstruction("JUMPZERO", temp, jump2, None, self._current_block))
        self.visit(forloop.body)

        if forloop.increment is not None:
            self.visit(forloop.increment)
        
        self.tac_list.append(TACInstruction("JUMP", jump1, None, None, self._current_block))
        self.tac_list.append(TACInstruction("LABEL", jump2, None, None, self._current_block))

        return "forloop"

    def visit_Return(self, returnn: Return):
        if self._return_label == None:
            self._return_label = self.generate_jump()
        self.tac_list.append(TACInstruction("RETURN", self.visit(returnn.expr), None, None, self._current_block))
        self.tac_list.append(TACInstruction("JUMP", self._return_label, None, None, self._current_block))
        return "return"

    def visit_WhileLoop(self, whileloop: WhileLoop):
        jump1 = self.generate_jump()
        self._current_block.addGlobal(jump1, (jump1, 0))
        jump2 = self.generate_jump()
        self._current_block.addGlobal(jump2, (jump2, 0))

        self.tac_list.append(TACInstruction("LABEL", jump1, None, None, self._current_block))
        temp = self.visit(whileloop.condition)
        self.tac_list.append(TACInstruction("JUMPZERO", temp, jump2, None, self._current_block))
        self.visit(whileloop.body)
        self.tac_list.append(TACInstruction("JUMP", jump1, None, None, self._current_block))
        self.tac_list.append(TACInstruction("LABEL", jump2, None, None, self._current_block))

        return "whileloop"

    def visit_Block(self, block: Block):

        temp = self._current_block
        self._current_block = CodeBlock(self._current_block)
        temp.addChild(self._current_block)
        
        for elem in block.var_decls:
            self.visit(elem)

        for elem in block.statements:
            self.visit(elem)

        self._current_block = temp
        return "block"

    def visit_Print(self, printt: Print):
        self.tac_list.append(TACInstruction('PRINT', self.visit(printt.expr), None, None, self._current_block))
        return 0

    def visit_IfElse(self, ifelse: IfElse):
        if ifelse.else_branch is None:
            jump = self.generate_jump()
            self._current_block.addGlobal(jump, (jump, 0))

            temp = self.visit(ifelse.condition)

            self.tac_list.append(TACInstruction("JUMPZERO", temp, jump, None, self._current_block))
            self.visit(ifelse.if_branch)
            self.tac_list.append(TACInstruction("LABEL", jump, None, None, self._current_block))
        else:
            jump1 = self.generate_jump()
            self._current_block.addGlobal(jump1, (jump1, 0))
            jump2 = self.generate_jump()
            self._current_block.addGlobal(jump2, (jump2, 0))

            temp = self.visit(ifelse.condition)

            self.tac_list.append(TACInstruction("JUMPZERO", temp, jump1, None, self._current_block))
            self.visit(ifelse.if_branch)
            self.tac_list.append(TACInstruction("JUMP", jump2, None, None, self._current_block))
            self.tac_list.append(TACInstruction("LABEL", jump1, None, None, self._current_block))
            self.visit(ifelse.else_branch)
            self.tac_list.append(TACInstruction("LABEL", jump2, None, None, self._current_block))
        return "ifelse"

    def visit_LBinary(self, lbinary: LBinary):
        temp = self.generate_temp()
        self._current_block.addVariable(temp, (self._frame_size, 1))
        self.tac_list.append(TACInstruction(lbinary.op, self.visit(lbinary.left), self.visit(lbinary.right), temp, self._current_block))

        return temp

    def visit_Comparison(self, comparison: Comparison):
        temp = self.generate_temp()
        self._current_block.addVariable(temp, (self._frame_size, 1))
        self.tac_list.append(TACInstruction(comparison.op, self.visit(comparison.left), self.visit(comparison.right), temp, self._current_block))
        return temp

    def visit_LLiteral(self, lliteral: LLiteral):
        return lliteral.value

    def visit_LPrimary(self, lprimary: LPrimary):
        temp = self.generate_temp()
        self._current_block.addVariable(temp, (self._frame_size, 1))
        self.tac_list.append(TACInstruction("BOOLCAST", self.visit(lprimary.primary), None, temp, self._current_block))

        return temp

    def visit_GetVector(self, getvector: GetVector):
        temp = self.generate_temp()
        self._current_block.addVariable(temp, (self._frame_size, 1))

        if isinstance(getvector.vector_index, ALiteral):
            self.tac_list.append(TACInstruction('GETVECTOR', getvector.identifier.name, getvector.vector_index.value, temp, self._current_block))
        else:
            self.tac_list.append(TACInstruction('GETVECTOR', getvector.identifier.name, self.visit(getvector.vector_index), temp, self._current_block))
        return temp

    def visit_Variable(self, variable: Variable):
        return variable.identifier.name

    def visit_LNot(self, lnot: LNot):
        if isinstance(lnot.right, LLiteral):
            return not self.visit(lnot.right)
        else:
            temp = self.generate_temp()
            self._current_block.addVariable(temp, (self._frame_size, 1))
            self.tac_list.append(TACInstruction('!', self.visit(lnot.right), None, temp, self._current_block))
            return temp

    def visit_ABinary(self, abinary: ABinary):
        al = self.visit(abinary.left)
        ar = self.visit(abinary.right)

        sizel = self._current_block.getVariable(al)[1]
        sizer = self._current_block.getVariable(ar)[1]

        if sizel > 1 or sizer > 1:
            temp = self.generate_temp()
            self._frame_size += 8 * max(sizel, sizer)
            self._current_block.addVariable(temp, (self._frame_size, max(sizel, sizer)))
            self.tac_list.append(TACInstruction('PUTADDRESS', temp, None, None, self._current_block))
        else:
            temp = self.generate_temp()
            self._current_block.addVariable(temp, (self._frame_size, 1))

        self.tac_list.append(TACInstruction(abinary.op, al, ar, temp, self._current_block))
        return temp

    def visit_AUMinus(self, auminus: AUMinus):
        if isinstance(auminus.right, ALiteral):
            return self.visit(auminus.right) * (-1)
        else:
            ar = self.visit(auminus.right)
            sizer = sizer = self._current_block.getVariable(ar)[1]

            if sizer > 1:
                temp = self.generate_temp()
                self._frame_size += 8 * sizer
                self._current_block.addVariable(temp, (self._frame_size, sizer))
                self.tac_list.append(TACInstruction('PUTADDRESS', temp, None, None, self._current_block))
            else:
                temp = self.generate_temp()
                self._current_block.addVariable(temp, (self._frame_size, 1))
            
            self.tac_list.append(TACInstruction('AUMINUS', self.visit(auminus.right), None, temp, self._current_block))
            return temp

    def visit_ALiteral(self, aliteral: ALiteral):
        return aliteral.value

    def visit_Call(self, call: Call):
        temp = self.generate_temp()
        self._current_block.addVariable(temp, (self._frame_size, 1))

        pairs = []
        for i in range(len(call.arguments)):
            param = self.visit(call.arguments[i])
            pairs.append(str(self._current_block.getVariable(param)[1]))
            self.tac_list.append(TACInstruction("PARAM", param, i, None, self._current_block))

        function_name = ''.join([call.callee.name, '.'] + pairs)
        if function_name not in self._functions_done:
            self._functions_wait.add(call.callee.name)
            if call.callee.name in self._functions:
                self._functions[call.callee.name].add(''.join(pairs))
            else:
                self._functions[call.callee.name] = set([''.join(pairs)])

        self.tac_list.append(TACInstruction("CALL", function_name, None, temp, self._current_block))

        return temp

##################################################################################################################

    def compile(self, ast: Program):
        self.visit(ast)

        prologue = '''#include "print.h"

    .global main'''

        self._text.append('''

    .text
    .align  2
main:''')

        self._data.append('''

    .data''')

        for tac in self.tac_list:
            arg1_adr = None
            arg2_adr = None
            res_adr = None

            arg1_size = None
            arg2_size = None
            res_size = None

            if tac.op == "CALL":
                arg1_adr = tac.arg1
            else:
                # arg1_adr calculation
                if tac.arg1 == None:
                    pass
                elif isinstance(tac.arg1, List):
                    arg1_adr = [tac.block.getVariable(elem)[0] for elem in tac.arg1]
                else:
                    tmp = tac.block.getVariable(tac.arg1)
                    arg1_adr = tmp[0]
                    arg1_size = tmp[1]

                # arg2_adr calculation
                if tac.arg2 == None:
                    pass
                elif isinstance(tac.arg2, List):
                    arg2_adr = [tac.block.getVariable(elem) for elem in tac.arg2]
                else:
                    tmp = tac.block.getVariable(tac.arg2)
                    arg2_adr = tmp[0]
                    arg2_size = tmp[1]

            # res_adr calculation
            if tac.result == None:
                pass
            else:
                tmp = tac.block.getVariable(tac.result)
                res_adr = tmp[0]
                res_size = tmp[1]

            if tac.op == None:
                pass

            # Global integer or bool declaration
            elif tac.op == 'GLOBAL_VAR_DECL':
                if isinstance(arg1_adr, float):
                    self._data.append(f'''
{res_adr}:
    .dword  {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    self._data.append(f'''
{res_adr}:
    .dword  0''')
                    self._text.append(f'''
        # {tac.result} = {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                if isinstance(arg1_adr, int):
                    self._data.append(f'''
{res_adr}:
    .dword  0''')
                    self._text.append(f'''
        # {tac.result} = {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                if arg1_adr is None:
                    self._data.append(f'''
{res_adr}:
    .dword  0''')

            # Global vector declaration
            # TODO: Check {i*8} stuff
            elif tac.op == 'GLOBAL_VEC_DECL':
                # Version with len
#                self._data.append(f'''
#    .dword  {len(arg1_adr)}
#{res_adr}:''')

                self._data.append(f'''
{res_adr}:
    .dword  0''')
                self._text.append(f'''
        # VEC INIT
    la      t0, {res_adr}
    addi    t1, t0, 8
    sd      t1, 0(t0)''')
                for i in range(0, len(arg1_adr)):
                    if isinstance(arg1_adr[i], float):
                        self._data.append(f'''
    .dword  {int(arg1_adr[i])}''')
                    elif isinstance(arg1_adr[i], str):
                        self._data.append(f'''
    .dword  0''')
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}
    la      t0, {arg1_adr[i]}
    ld      t0, 0(t0)
    la      t1, {res_adr}
    sd      t0, {(i+1)*8}(t1)''')
                    elif isinstance(arg1_adr[i], int):
                        self._data.append(f'''
    .dword  0''')
                        self._text.append(f'''
        # {tac.result} = {arg1_adr[i]}
    ld      t0, -{arg1_adr[i]}(fp)
    la      t1, {res_adr}
    sd      t0, {(i+1)*8}(t1)''')
                    else:
                        self._data.append(f'''
    .dword  0''')

            # String
            elif tac.op == 'GLOBAL_STR_DECL':
                self._data.append(f'''
{res_adr}:
    .string "{tac.arg1}"''')

            # Vector GET single index
            elif tac.op == 'GETVECTOR':
                if isinstance(arg1_adr, float):
                    print("ERROR: INDEXING CONSTANT")

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t0, {int(arg2_adr) * 8}(t0)''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slli    t1, t1, 3
    add     t0, t0, t1
    ld      t0, 0(t0)''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    slli    t1, t1, 3
    add     t0, t0, t1
    ld      t0, 0(t0)''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    ld      t0, -{arg1_adr}(fp)
    ld      t0, {int(arg2_adr) * 8}(t0)''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slli    t1, t1, 3
    add     t0, t0, t1
    ld      t0, 0(t0)''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    slli    t1, t1, 3
    add     t0, t0, t1
    ld      t0, 0(t0)''')


                if isinstance(res_adr, str):
                    print("ERROR: SOMETHING WENT WRONG")

                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Vector SET single index
            elif tac.op == 'SETVECTOR':
                
                if isinstance(res_adr, float):
                    self._text.append(f'''
        # {tac.arg1}[{tac.arg2}] = {tac.result}
    li      t2, {int(res_adr)}''')
                if isinstance(res_adr, str):
                    self._text.append(f'''
        # {tac.arg1}[{tac.arg2}] = {tac.result}
    la      t2, {res_adr}
    ld      t2, 0(t2)''')
                if isinstance(res_adr, int):
                    self._text.append(f'''
        # {tac.arg1}[{tac.arg2}] = {tac.result}
    ld      t2, -{res_adr}(fp)''')

                if isinstance(arg1_adr, float):
                    print("ERROR: INDEXING CONSTANT")

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    sd      t2, {int(arg2_adr) * 8}(t0)''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slli    t1, t1, 3
    add     t0, t0, t1
    sd      t2, 0(t0)''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    slli    t1, t1, 3
    add     t0, t0, t1
    sd      t2, 0(t0)''')

                # TODO: For stack kept vectors
                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
    ld      t0, -{arg1_adr}(fp)
    sd      t2, {int(arg2_adr) * 8}(t0)''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slli    t1, t1, 3
    add     t0, t0, t1
    sd      t2, 0(t0)''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}[{tac.arg2}]
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    slli    t1, t1, 3
    add     t0, t0, t1
    sd      t2, 0(t0)''')

            elif tac.op == 'PUTADDRESS':
                self._text.append(f'''
        # STACK VEC INIT 
    mv      t0, fp
    addi    t0, t0, -{arg1_adr - 8}
    sd      t0, -{arg1_adr}(fp)''')

            # Assignment
            elif tac.op == '=':

                if arg1_size != res_size:
                    print("ERROR: INVALID ASSIGNMENT")
                
                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # {tac.result} = {tac.arg1}
    li      t0, {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    if arg1_size == 1 and res_size == 1:
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)''')
                    if arg1_size > 1 and res_size > 1:
                        if isinstance(res_adr, str):
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t3, {res_adr}
    ld      t3, 0(t3)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                        if isinstance(res_adr, int):
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                if isinstance(arg1_adr, int):
                    if arg1_size == 1 and res_size == 1:
                        self._text.append(f'''
        # {tac.result} = {tac.arg1}
    ld      t0, -{arg1_adr}(fp)''')
                    if arg1_size > 1 and res_size > 1:
                        if isinstance(res_adr, str):
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t3, {res_adr}
    ld      t3, 0(t3)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                        if isinstance(res_adr, int):
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Summation
            elif tac.op == '+':

                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    li      t0, {int(arg1_adr)}
    addi    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    addi    t0, t0, {int(arg1_adr)}''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    ld      t0, -{arg2_adr}(fp)
    addi    t0, t0, {int(arg1_adr)}''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    addi    t0, t0, {int(arg2_adr)}''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    add     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vle64.v v2, (t2)
    vadd.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    add     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vle64.v v2, (t2)
    vadd.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    addi    t0, t0, {int(arg2_adr)}''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
    
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    add     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vle64.v v2, (t2)
    vadd.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} + {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    add     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} + {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] + {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t4)
    vle64.v v2, (t2)
    vadd.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Subtraction
            elif tac.op == '-':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    li      t0, {int(arg1_adr)}
    addi    t0, t0, -{int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg1_adr)}
    neg     t0, t0''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    ld      t0, -{arg2_adr}(fp)
    addi    t0, t0, -{int(arg1_adr)}
    neg     t0, t0''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg2_adr)}''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vsub.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vsub.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    addi    t0, t0, -{int(arg2_adr)}''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vsub.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} - {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} - {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vadd.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vsub.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] - {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vsub.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Multiplication
            elif tac.op == '*':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    li      t0, {int(arg1_adr)}
    li      t1, {int(arg2_adr)}
    mul     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    mul     t0, t0, t1''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    mul     t0, t0, t1''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    li      t4, {int(arg1_adr)}
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    li      t1, {int(arg2_adr)}
    mul     t0, t0, t1''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    mul     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vmul.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    mul     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vmul.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    li      t1, {int(arg2_adr)}
    mul     t0, t0, t1''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    mul     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vmul.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} * {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    mul     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} * {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmul.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] * {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vmul.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Division
            elif tac.op == '/':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    li      t0, {int(arg1_adr)}
    li      t1, {int(arg2_adr)}
    div     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    div     t0, t0, t1''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
    li      t4, {int(arg1_adr)}
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vmv.v.x v2, t4
    vle64.v v0, (t2)
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                    if isinstance(arg2_adr, int):
                        if arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    div     t0, t0, t1''')
                        if arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
    li      t4, {int(arg1_adr)}
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vmv.v.x v2, t4
    vle64.v v0, (t2)
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    li      t1, {int(arg2_adr)}
    div     t0, t0, t1''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    div     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmv.v.x v2, t4
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vdiv.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    div     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    la      t4, {arg1_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmv.v.x v2, t4
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vdiv.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        if arg1_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    li      t1, {int(arg2_adr)}
    div     t0, t0, t1''')
                        if arg1_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    li      t4, {int(arg2_adr)}
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t4, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, str):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    div     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    la      t2, {arg2_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmv.v.x v2, t4
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}[]
    li      t1, {int(arg1_size)}
    la      t4, {arg2_adr}
    ld      t4, 0(t4)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vdiv.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')
                    if isinstance(arg2_adr, int):
                        if arg1_size == 1 and arg2_size == 1:
                            self._text.append(f'''
        # {tac.result} = {tac.arg1} / {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    div     t0, t0, t1''')
                        if arg1_size == 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1} / {tac.arg2}[]
    li      t1, {int(arg2_size)}
    ld      t4, -{arg1_adr}(fp)
    ld      t2, -{arg2_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vmv.v.x v2, t4
    vdiv.vv v0, v2, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size == 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vdiv.vx v0, v0, t4
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    bgtz    t1, {label}''')
                        if arg1_size > 1 and arg2_size > 1:
                            label = self.generate_vector()
                            self._text.append(f'''
        # {tac.result}[] = {tac.arg1}[] / {tac.arg2}[]
    li      t1, {int(arg1_size)}
    ld      t4, -{arg2_adr}(fp)
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vle64.v v2, (t4)
    vdiv.vv v0, v0, v2
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t5, t0, 3
    add     t2, t2, t5
    add     t3, t3, t5
    add     t4, t4, t5
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Unary minus
            elif tac.op == 'AUMINUS':
                if isinstance(arg1_adr, float):
                    print("ERROR: OPTIMIZED CASE")
                if isinstance(arg1_adr, str):
                    if arg1_size == 1:
                        self._text.append(f'''
        # {tac.result} = - {tac.arg1}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    neg     t0, t0''')
                    if arg1_size > 1:
                        label = self.generate_vector()
                        self._text.append(f'''
        # {tac.result}[] = - {tac.arg1}[]
    li      t1, {int(arg1_size)}
    la      t2, {arg1_adr}
    ld      t2, 0(t2)
    ld      t3, -{res_adr}(fp)
{label}:
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t4, t0, 3
    add     t2, t2, t4
    add     t3, t3, t4
    bgtz    t1, {label}''')
                if isinstance(arg1_adr, int):
                    if arg1_size == 1:
                        self._text.append(f'''
        # {tac.result} = - {tac.arg1}
    ld      t0, -{arg1_adr}(fp)
    neg     t0, t0''')
                    if arg1_size > 1:
                        label = self.generate_vector()
                        self._text.append(f'''
        # {tac.result}[] = - {tac.arg1}[]
    li      t1, {int(arg1_size)}
    ld      t2, -{arg1_adr}(fp)
    ld      t3, -{res_adr}(fp)
{label}:    
    vsetvli t0, t1, e64, m2, tu, mu
    vle64.v v0, (t2)
    vneg.v  v0, v0
    vse64.v v0, (t3)
    sub     t1, t1, t0
    slli    t4, t0, 3
    add     t2, t2, t4
    add     t3, t3, t4
    bgtz    t1, {label}''')

                if res_size == 1:
                    if isinstance(res_adr, str):
                        self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                    else:
                        self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # Logical Not
            elif tac.op == '!':
                if isinstance(arg1_adr, float):
                    print("ERROR: OPTIMIZED CASE")
                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # {tac.result} = - {tac.arg1}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    seqz    t0, t0''')
                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # {tac.result} = - {tac.arg1}
    ld      t0, -{arg1_adr}(fp)
    seqz    t0, t0''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # EQ
            elif tac.op == '==':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    li      t0, {int(arg1_adr)}
    addi    t0, t0, -{int(arg2_adr)}
    seqz    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg1_adr)}
    seqz    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg2_adr}(fp)
    addi    t0, t0, -{int(arg1_adr)}
    seqz    t0, t0''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg2_adr)}
    seqz    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1
    seqz    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1
    seqz    t0, t0''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    addi    t0, t0, -{int(arg2_adr)}
    seqz    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1
    seqz    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1
    seqz    t0, t0''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # NEQ
            elif tac.op == '!=':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    li      t0, {int(arg1_adr)}
    addi    t0, t0, -{int(arg2_adr)}
    snez    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg1_adr)}
    snez    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg2_adr}(fp)
    addi    t0, t0, -{int(arg1_adr)}
    snez    t0, t0''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    addi    t0, t0, -{int(arg2_adr)}
    snez    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1
    snez    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1
    snez    t0, t0''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    addi    t0, t0, -{int(arg2_adr)}
    snez    t0, t0''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sub     t0, t0, t1
    snez    t0, t0''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} == {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    sub     t0, t0, t1
    snez    t0, t0''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # L
            elif tac.op == '<':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # G
            elif tac.op == '>':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    li      t0, {int(arg1_adr)}
    li      t1, {int(arg2_adr)}
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    li      t1, {int(arg2_adr)}
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    li      t1, {int(arg2_adr)}
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} > {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')

            # LE
            elif tac.op == '<=':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    li      t0, {int(arg1_adr)}
    li      t1, {int(arg2_adr)}
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    li      t1, {int(arg2_adr)}
    sgt    t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    li      t1, {int(arg2_adr)}
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    sgt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} <= {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    sgt     t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    seqz    t0, t0
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    seqz    t0, t0
    sd      t0, -{res_adr}(fp)''')

            # GE
            elif tac.op == '>=':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    li      t0, {int(arg1_adr)}
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    slti    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    la      t1, {arg2_adr}
    ld      t1, 0(t1)
    slt     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} < {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    ld      t1, -{arg2_adr}(fp)
    slt     t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    seqz    t0, t0
    sd      t0, 0(t1)''')

                else:
                    self._text.append(f'''
    seqz    t0, t0
    sd      t0, -{res_adr}(fp)''')

            elif tac.op == 'BOOLCAST':
                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # CAST {tac.arg1}
    li      t0, {int(arg1_adr)}
    snez    t0, t0
    sd      t0, -{res_adr}(fp)''')

                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # CAST {tac.arg1}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    snez    t0, t0
    sd      t0, -{res_adr}(fp)''')

                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # CAST {tac.arg1}
    ld      t0, -{arg1_adr}(fp)
    snez    t0, t0
    sd      t0, -{res_adr}(fp)''')
            
            elif tac.op == 'and':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    li      t0, {int(arg2_adr)}
    andi    t0, t0, {int(arg1_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    andi    t0, t0, {int(arg1_adr)}''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    ld      t0, -{arg2_adr}(fp)
    andi    t0, t0, {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    andi    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    la      t1, {int(arg2_adr)}
    ld      t1, 0(t1)
    and     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    ld      t1, -{int(arg2_adr)}(fp)
    and     t0, t0, t1''')
                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    andi    t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    la      t1, {int(arg2_adr)}
    ld      t1, 0(t1)
    and     t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} and {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    ld      t1, -{int(arg2_adr)}(fp)
    and     t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')
            
            elif tac.op == 'or':
                if isinstance(arg1_adr, float):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    li      t0, {int(arg2_adr)}
    ori     t0, t0, {int(arg1_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    la      t0, {arg2_adr}
    ld      t0, 0(t0)
    ori     t0, t0, {int(arg1_adr)}''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    ld      t0, -{arg2_adr}(fp)
    ori     t0, t0, {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    ori     t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    la      t1, {int(arg2_adr)}
    ld      t1, 0(t1)
    or      t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    la      t0, {int(arg1_adr)}
    ld      t0, 0(t0)
    ld      t1, -{int(arg2_adr)}(fp)
    or      t0, t0, t1''')
                if isinstance(arg1_adr, int):
                    if isinstance(arg2_adr, float):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    ori     t0, t0, {int(arg2_adr)}''')
                    if isinstance(arg2_adr, str):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    la      t1, {int(arg2_adr)}
    ld      t1, 0(t1)
    or      t0, t0, t1''')
                    if isinstance(arg2_adr, int):
                        self._text.append(f'''
        # {tac.result} = {tac.arg1} or {tac.arg1}
    ld      t0, -{int(arg1_adr)}(fp)
    ld      t1, -{int(arg2_adr)}(fp)
    or      t0, t0, t1''')

                if isinstance(res_adr, str):
                    self._text.append(f'''
    la      t1, {res_adr}
    sd      t0, 0(t1)''')
                else:
                    self._text.append(f'''
    sd      t0, -{res_adr}(fp)''')



            elif tac.op == 'JUMPZERO':
                # assuming temp in stack, jump is label

                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # JUMP {tac.arg2}
    li      t0, {int(arg1_adr)}
    beqz    t0, {arg2_adr}''')

                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # JUMP {tac.arg2}
    la      t0, {arg1_adr}
    ld      t0, 0(t0)
    beqz    t0, {arg2_adr}''')

                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # JUMP {tac.arg2}
    ld      t0, -{arg1_adr}(fp)
    beqz    t0, {arg2_adr}''')

            elif tac.op == 'LABEL':
                self._text.append(f'''
{arg1_adr}:''')

            elif tac.op == 'JUMP':
                self._text.append(f'''
        # JUMP {tac.arg1}
    beqz    zero, {arg1_adr}''')

            elif tac.op == 'PARAM':
                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # PARAM {tac.arg1}
    li      a{int(arg2_adr)}, {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # PARAM {tac.arg1}
    la      a{int(arg2_adr)}, {arg1_adr}
    ld      a{int(arg2_adr)}, 0(a{int(arg2_adr)})''')
                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # PARAM {tac.arg1}
    ld      a{int(arg2_adr)}, -{arg1_adr}(fp)''')

            elif tac.op == 'GETPARAM':
                    self._text.append(f'''
        # PARAM {tac.arg1}
    sd      a{int(arg1_adr)}, -{res_adr}(fp)''')

            elif tac.op == 'CALL':
                self._text.append(f'''
        # {tac.result} = CALL {tac.arg1}
    call    {arg1_adr}
    sd      a0, -{res_adr}(fp)''')

            elif tac.op == 'RETURN':
                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # RETURN {tac.arg1}
    li      a0, {int(arg1_adr)}''')
                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # RETURN {tac.arg1}
    la      a0, {arg1_adr}
    ld      a0, 0(a0)''')
                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # RETURN {tac.arg1}
    ld      a0, -{arg1_adr}(fp)''')

            elif tac.op == 'STACKUP':
                self._text.append(f'''
        # STACK UP
    addi    sp, sp, -{int(arg1_adr)}
    sd      ra, {int(arg1_adr-8)}(sp)
    sd      fp, {int(arg1_adr-16)}(sp)
    addi    fp, sp, {int(arg1_adr)}''')

            elif tac.op == 'STACKDOWN':
                self._text.append(f'''
        # STACK DOWN
    ld      ra, {int(arg1_adr-8)}(sp)
    ld      fp, {int(arg1_adr-16)}(sp)
    addi    sp, sp, {int(arg1_adr)}
    ret
''')

            # Print
            elif tac.op == 'PRINT':
                if isinstance(arg1_adr, float):
                    self._text.append(f'''
        # PRINT {tac.arg1}
    addi    sp, sp, -8
    li      t0, {int(arg1_adr)}
    sd      t0, 0(sp)
    mv      a1, sp
    li      a0, {arg1_size}
    call    __vox_print__
    addi    sp, sp, 8''')
                if isinstance(arg1_adr, str):
                    self._text.append(f'''
        # PRINT {tac.arg1}
    la      a1, {arg1_adr}
    li      a0, {arg1_size}
    call    __vox_print__''')
                if isinstance(arg1_adr, int):
                    self._text.append(f'''
        # PRINT {tac.arg1}
    mv      a1, fp
    addi    a1, a1, -{arg1_adr}
    li      a0, {arg1_size}
    call    __vox_print__''')

        with open('dump.s', 'w') as dump:
            dump.write(prologue)
            dump.write("".join(self._data))
            dump.write("".join(self._text))
