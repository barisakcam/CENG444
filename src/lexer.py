import sly

class Lexer(sly.Lexer):
    tokens = { NUMBER, ID, WHILE, IF, ELSE, PRINT,
               PLUS, MINUS, TIMES, DIVIDE, ASSIGN,
               EQ, LT, LE, GT, GE, NE, AND,
               FALSE, TRUE, FUN, FOR, OR,
               RETURN, VAR, STRING, NOT }

    #LE := <=
    #EQ := ==
    #LT := <
    #GT := >
    #GE := >=
    #NE := !=

    #Sanitize your tokens for the literals in the language (not token literals)!
    #each token t for NUMBER should have type(t.value) == float
    #each token t for STRING should have type(t.value) == str (remove the quotes!)
    #each token t for TRUE/FALSE should have type(t.value) == bool

    literals = { '(', ')', '{', '}', '[', ']', ';' , ',', '#'}

    #Do not modify the sets Lexer.literals and Lexer.tokens!

    ignore = ' \t'
    ignore_comment = r'\/\/.*'

    PLUS = r'\+'
    MINUS = r'-'
    TIMES = r'\*'
    DIVIDE = r'/'
    EQ = r'=='
    LE = r'<='
    GE = r'>='
    NE = r'!='
    ASSIGN = r'='
    LT = r'<'
    GT = r'>'
    NOT = r'!'

    ID =  r'[a-zA-Z_][a-zA-Z0-9_]*'
    ID['if'] = IF
    ID['else'] = ELSE
    ID['print'] = PRINT
    ID['for'] = FOR
    ID['while'] = WHILE
    ID['var'] = VAR
    ID['return'] = RETURN
    ID['fun'] = FUN
    ID['and'] = AND
    ID['or'] = OR
    ID['true'] = TRUE
    ID['false'] = FALSE

    @_(r'\d+\.\d+|\d+')
    def NUMBER(self, t):
        t.value = float(t.value)
        return t

    @_(r'"[^"\\]*(\\.[^"\\]*)*"')
    def STRING(self, t):
        t.value = str(t.value[1:-1])
        return t

    @_(r'true')
    def TRUE(self, t):
        t.value = True
        return t

    @_(r'false')
    def FALSE(self, t):
        t.value = False
        return t
    
    @_(r'\n')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    def error(self, t):
        self.index += 1
        t.value = t.value[0:1]
        return t

