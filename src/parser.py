import sly
import lexer
import ast_tools

class Parser(sly.Parser):
    debugfile = 'parser.dbg'
    tokens = lexer.Lexer.tokens

    @_('VARDECLS FUNDECLS FREE_STATEMENTS EOF')
    def PROGRAM(self, p):
        return ast_tools.Program(p.VARDECLS, p.FUNDECLS, p.FREE_STATEMENTS)

    @_('VARDECLS VARDECL')
    def VARDECLS(self, p):
        return p.VARDECLS + [p.VARDECL]

    @_('')
    def VARDECLS(self, p):
        return []

    @_('FUNDECLS FUNDECL')
    def FUNDECLS(self, p):
        return p.FUNDECLS + [p.FUNDECL]

    @_('')
    def FUNDECLS(self, p):
        return []

    @_('FREE_STATEMENTS FREE_STATEMENT')
    def FREE_STATEMENTS(self, p):
        return p.FREE_STATEMENTS + [p.FREE_STATEMENT]

    #@_('ERRORSTMT')
    #def FREE_STATEMENTS(self, p):
    #    return

    @_('')
    def FREE_STATEMENTS(self, p):
        return []

    @_('')
    def EOF(self, p):
        return None

####################################################

    #@_('VAR ID')
    #def VARDECL(self, p):
    #   return VarDecl(p.ID, None)
    
    @_('VAR ID [ ASSIGN INIT ] ";"')
    def VARDECL(self, p):
        return ast_tools.VarDecl(ast_tools.Identifier(p.ID, p.lineno, p.index), p.INIT)
   
    @_('FUN FUNCTION')
    def FUNDECL(self, p):
        return p.FUNCTION  #FUNCTION will return FunDecl()

####################################################

    @_('SIMPLESTMT ";"')
    def FREE_STATEMENT(self, p):
        return p.SIMPLESTMT

    @_('COMPOUNDSTMT')
    def FREE_STATEMENT(self, p):
        return p.COMPOUNDSTMT

    @_('error ";"')
    def FREE_STATEMENT(self, p):
        #print(f"Whoops error: {p.lineno}")
        return ast_tools.ErrorStmt()

    @_('error "}"')
    def FREE_STATEMENT(self, p):
        #print(f"Whoops error: {p.lineno}")
        return ast_tools.ErrorStmt()

#######################################################

    @_('EXPR')
    def INIT(self, p):
        return p.EXPR #???

    @_('"[" EXPR EXPRS "]"')
    def INIT(self, p):
        return [p.EXPR] + p.EXPRS #???

    @_('"," EXPR EXPRS')
    def EXPRS(self, p):
        return [p.EXPR] + p.EXPRS

    @_('')
    def EXPRS(self, p):
        return []

##########################################################

    @_('ASGNSTMT')
    def SIMPLESTMT(self, p):
        return p.ASGNSTMT

    @_('PRINTSTMT')
    def SIMPLESTMT(self, p):
        return p.PRINTSTMT

    @_('RETURNSTMT')
    def SIMPLESTMT(self, p):
        return p.RETURNSTMT

############################################################

    @_('IFSTMT')
    def COMPOUNDSTMT(self, p):
        return p.IFSTMT

    @_('WHILESTMT')
    def COMPOUNDSTMT(self, p):
        return p.WHILESTMT

    @_('FORSTMT')
    def COMPOUNDSTMT(self, p):
        return p.FORSTMT

#############################################################

    @_('FREE_STATEMENT')
    def STATEMENT(self, p):
        return p.FREE_STATEMENT

    @_('BLOCK')
    def STATEMENT(self, p):
        return p.BLOCK

############################################################

    #@_('ID ASSIGN EXPR')
    #def ASGNSTMT(self, p):
    #    return Assign(p.ID, p.EXPR)

    @_('ID [ "[" AEXPR "]" ] ASSIGN EXPR')
    def ASGNSTMT(self, p):
        if p.AEXPR is None:
            return ast_tools.Assign(ast_tools.Identifier(p.ID, p.lineno, p.index), p.EXPR)
        else:
            return ast_tools.SetVector(ast_tools.Identifier(p.ID, p.lineno, p.index), p.AEXPR, p.EXPR)

    @_('PRINT EXPR')
    def PRINTSTMT(self, p):
        return ast_tools.Print(p.EXPR)

    @_('RETURN EXPR')
    def RETURNSTMT(self, p):
        return ast_tools.Return(p.EXPR)

###############################################################

    @_('IF LEXPR STATEMENT [ ELSE STATEMENT ]')
    def IFSTMT(self, p):
        if p.ELSE is None:
            return ast_tools.IfElse(p.LEXPR, p.STATEMENT0, None)
        else:
            return ast_tools.IfElse(p.LEXPR, p.STATEMENT0, p.STATEMENT1)

    #@_('IF LEXPR STATEMENT')
    #def IFSTMT(self, p):
    #    return IfElse()

    @_('WHILE LEXPR STATEMENT')
    def WHILESTMT(self, p):
        return ast_tools.WhileLoop(p.LEXPR, p.STATEMENT)

    @_('FOR "(" [ ASGNSTMT ] ";" [ LEXPR ] ";" [ ASGNSTMT ] ")" STATEMENT')
    def FORSTMT(self, p):
        return ast_tools.ForLoop(p.ASGNSTMT0, p.LEXPR, p.ASGNSTMT1, p.STATEMENT)

##################################################################

    @_('"{" VARDECLS STATEMENTS "}"')
    def BLOCK(self, p):
        return ast_tools.Block(p.VARDECLS, p.STATEMENTS)

    @_('STATEMENTS STATEMENT')
    def STATEMENTS(self, p):
        return p.STATEMENTS + [p.STATEMENT]

    @_('')
    def STATEMENTS(self, p):
        return []

#######################################################################

    @_('LEXPR')
    def EXPR(self, p):
        return p.LEXPR

    @_('AEXPR')
    def EXPR(self, p):
        return p.AEXPR

    @_('SEXPR')
    def EXPR(self, p):
        return p.SEXPR

#########################################################################

    @_('LEXPR OR LTERM')
    def LEXPR(self, p):
        return ast_tools.LBinary("or", p.LEXPR, p.LTERM)

    @_('LTERM')
    def LEXPR(self, p):
        return p.LTERM

    @_('LTERM AND LFACT')
    def LTERM(self, p):
        return ast_tools.LBinary("and", p.LTERM, p.LFACT)

    @_('LFACT')
    def LTERM(self, p):
        return p.LFACT

    @_('CEXPR')
    def LFACT(self, p):
        return p.CEXPR

    @_('"#" CALL')
    def LFACT(self, p):
        return ast_tools.LPrimary(p.CALL)

    @_('"(" LEXPR ")"')
    def LFACT(self, p):
        return p.LEXPR

    @_('"#" ID [ "[" AEXPR "]" ]')
    def LFACT(self, p):
        if p.AEXPR is None:
            return ast_tools.LPrimary(ast_tools.Variable(ast_tools.Identifier(p.ID, p.lineno, p.index)))
        else:
            return ast_tools.LPrimary(ast_tools.GetVector(ast_tools.Identifier(p.ID, p.lineno, p.index), p.AEXPR))

    @_('NOT LFACT')
    def LFACT(self, p):
        return ast_tools.LNot(p.LFACT)

    @_('TRUE')
    def LFACT(self, p):
        return ast_tools.LLiteral(p.TRUE)  #!!!

    @_('FALSE')
    def LFACT(self, p):
        return ast_tools.LLiteral(p.FALSE)  #!!!

#################################################################

    @_('AEXPR PLUS TERM')
    def AEXPR(self, p):
        return ast_tools.ABinary("+", p.AEXPR, p.TERM)

    @_('AEXPR MINUS TERM')
    def AEXPR(self, p):
        return ast_tools.ABinary('-', p.AEXPR, p.TERM)

    @_('TERM')
    def AEXPR(self, p):
        return p.TERM

    @_('TERM DIVIDE FACT')
    def TERM(self, p):
        return ast_tools.ABinary("/", p.TERM, p.FACT)

    @_('TERM TIMES FACT')
    def TERM(self, p):
        return ast_tools.ABinary("*", p.TERM, p.FACT)

    @_('FACT')
    def TERM(self, p):
        return p.FACT

    @_('MINUS FACT')
    def FACT(self, p):
        return ast_tools.AUMinus(p.FACT)

    @_('CALL')
    def FACT(self, p):
        return p.CALL

    @_('NUMBER')
    def FACT(self, p):
        return ast_tools.ALiteral(p.NUMBER)  #!!!

    @_('"(" AEXPR ")"')
    def FACT(self, p):
        return p.AEXPR

    @_('ID [ "[" AEXPR "]" ]')
    def FACT(self, p):
        if p.AEXPR is None:
            return ast_tools.Variable(ast_tools.Identifier(p.ID, p.lineno, p.index))  #!!!
        else:
            return ast_tools.GetVector(ast_tools.Identifier(p.ID, p.lineno, p.index), p.AEXPR)

#########################################################

    @_('AEXPR NE AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison("!=", p.AEXPR0, p.AEXPR1)

    @_('AEXPR EQ AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison("==", p.AEXPR0, p.AEXPR1)

    @_('AEXPR GT AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison(">", p.AEXPR0, p.AEXPR1)

    @_('AEXPR GE AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison(">=", p.AEXPR0, p.AEXPR1)

    @_('AEXPR LT AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison("<", p.AEXPR0, p.AEXPR1)

    @_('AEXPR LE AEXPR')
    def CEXPR(self, p):
        return ast_tools.Comparison("<=", p.AEXPR0, p.AEXPR1)

###########################################################

    @_('STRING')
    def SEXPR(self, p):
        return ast_tools.SLiteral(p.STRING)

###############################################################

    @_('EXPR EXPRS')
    def ARGUMENTS(self, p):
        return [p.EXPR] + p.EXPRS
    
    @_('ID "(" [ PARAMETERS ] ")" BLOCK')
    def FUNCTION(self, p):
        if p.PARAMETERS is None:
            return ast_tools.FunDecl(ast_tools.Identifier(p.ID, p.lineno, p.index), [], p.BLOCK)
        else:
            return ast_tools.FunDecl(ast_tools.Identifier(p.ID, p.lineno, p.index), p.PARAMETERS, p.BLOCK)

    @_('ID IDS')
    def PARAMETERS(self, p):
        return [ast_tools.Identifier(p.ID, p.lineno, p.index)] + p.IDS

    @_('"," ID IDS')
    def IDS(self, p):
        return [ast_tools.Identifier(p.ID, p.lineno, p.index + 1)] + p.IDS

    @_('')
    def IDS(self, p):
        return []

    @_('ID "(" [ ARGUMENTS ] ")"')
    def CALL(self, p):
        if p.ARGUMENTS is None:
            return ast_tools.Call(ast_tools.Identifier(p.ID, p.lineno, p.index), [])
        else:
            return ast_tools.Call(ast_tools.Identifier(p.ID, p.lineno, p.index), p.ARGUMENTS)
