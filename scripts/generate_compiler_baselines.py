#!/usr/bin/env python3
"""Independent bounded grammar oracle and handwritten RAM-machine assembly.

No Trident compiler invocation or compiler-generated assembly is used here.
See baselines/triton/std/compiler/README.md for the deliberately explicit scope.
"""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1] / 'baselines/triton'
P, N, C, START, KIND, VALUE, TCOUNT, POS, ACOUNT, TMP = range(3000000, 3000010)
SRC, TOK, AST = 3010000, 3020000, 3030000

def ld(a): return f'push {a} read_mem 1 pop 1'
def st(a): return f'push {a} write_mem 1 pop 1'
def put(a,v): return f'push {v} {st(a)}'
def inc(a): return f'{ld(a)} push 1 add {st(a)}'
def tok(f=0): return f'{ld(POS)} push 4 mul push {TOK+f} add read_mem 1 pop 1'
def node(f=0): return f'{ld(ACOUNT)} push 8 mul push {AST+f} add'
def eq(v): return f'{ld(C)} push {v} eq'
def member(chars): return '\n'.join([eq(ord(c)) for c in chars])+ '\nadd'*(len(chars)-1)
WORDS='program module use fn pub sec let mut const struct if else for in bounded return true false event reveal seal match Field XField Bool U32 Digest'.split()
SYMBOLS={'(':28,')':29,'{':30,'}':31,'[':32,']':33,',':34,':':35,';':36,'.':37,'=':40,'+':43,'*':44,'<':46,'>':47,'&':48,'^':49,'#':51,'_':52}

def lexer():
    a=['__read_source:',f'read_io 1 {st(N)} push 1025 {ld(N)} lt assert',put(P,0),'call __read_loop',put(P,0),put(TCOUNT,0),'call __lex_loop',put(KIND,56),f'{ld(P)} {st(START)}',put(VALUE,0),'call __emit_token','return',
       '__read_loop:',f'{ld(P)} {ld(N)} eq skiz return',f'read_io 1 {ld(P)} push {SRC} add write_mem 1 pop 1',inc(P),'recurse',
       '__peek:',f'{ld(P)} push {SRC} add read_mem 1 pop 1 {st(C)} return',
       '__lex_loop:',f'{ld(P)} {ld(N)} eq skiz return','call __peek',f'{ld(P)} {st(START)}',put(KIND,0),put(VALUE,0),member(' \n\r\t'),'skiz call __space',f'{ld(KIND)} push 999 eq skiz recurse','call __is_digit','skiz call __number',f'{ld(KIND)} push 0 eq skiz call __not_number','call __emit_token','recurse',
       '__space:',inc(P),put(KIND,999),'return',
       '__is_digit:',f'push 58 {ld(C)} lt {ld(C)} push 47 lt mul return',
       '__is_alpha:',f'push 123 {ld(C)} lt {ld(C)} push 96 lt mul push 91 {ld(C)} lt {ld(C)} push 64 lt mul add {eq(95)} add return',
       '__number:',put(KIND,53),'call __number_loop','return',
       '__number_loop:',f'{ld(P)} {ld(N)} eq skiz return','call __peek','call __is_digit','push 0 eq skiz return',f'{ld(VALUE)} push 10 mul {ld(C)} push -48 add add {st(VALUE)}',inc(P),'recurse',
       '__not_number:','call __is_alpha','skiz call __ident',f'{ld(KIND)} push 0 eq skiz call __symbol','return',
       '__ident:',put(KIND,54),'call __ident_loop']
    for i,w in enumerate(WORDS,1): a += [f'{ld(P)} {ld(START)} push -1 mul add push {len(w)} eq skiz call __word_{i}']
    a += ['return','__ident_loop:',f'{ld(P)} {ld(N)} eq skiz return','call __peek','call __is_alpha','call __is_digit','add push 0 eq skiz return',inc(P),'recurse']
    for i,w in enumerate(WORDS,1):
        a += [f'__word_{i}:']
        for j,c in enumerate(w): a += [f'{ld(START)} push {SRC+j} add read_mem 1 pop 1 push {ord(c)} eq push 0 eq skiz return']
        a += [put(KIND,i),'return']
    a += ['__symbol:']
    for c,k in SYMBOLS.items(): a += [f'{eq(ord(c))} skiz call __sym_{k}']
    a += [f'{eq(45)} skiz call __arrow',f'{ld(KIND)} push 0 eq push 0 eq assert',inc(P),'return']
    for c,k in SYMBOLS.items(): a += [f'__sym_{k}:',put(KIND,k),'return']
    a += ['__arrow:',inc(P),'call __peek',f'{eq(62)} assert',put(KIND,39),'return','__emit_token:']
    for j,var in enumerate([KIND,START,P,VALUE]): a += [f'{ld(var)} {ld(TCOUNT)} push 4 mul push {TOK+j} add write_mem 1 pop 1']
    a += [inc(TCOUNT),'return','__lexer_main:','call __read_source',f'{ld(TCOUNT)} write_io 1 push 0 write_io 1',put(POS,0),'call __tokens_out','return','__tokens_out:',f'{ld(POS)} {ld(TCOUNT)} eq skiz return']
    for j in range(4): a += [f'{tok(j)} write_io 1']
    a += [inc(POS),'recurse']
    return '\n'.join(a)+'\n'

def parser():
    a=['__parse:',put(POS,0)]
    for k in [1,54,4,54,28,29,39,23,30]: a += [f'{tok()} push {k} eq assert',inc(POS)]
    records=[[1,1,1,1,0,1,1,0],[3,3,2,0,2,3,0,0],[10,0,0,0,0,0,0,0],[26,4,0,0,0,0,0,0]]
    for i,r in enumerate(records):
        for j,v in enumerate(r): a += [put(AST+8*i+j,v)]
    a += [put(ACOUNT,4),'call __add_expr',st(AST+27)]
    for k in [31,56]: a += [f'{tok()} push {k} eq assert',inc(POS)]
    a += ['return','__add_expr:','call __mul_expr','call __add_tail','return','__add_tail:',f'{tok()} push 43 eq push 0 eq skiz return',inc(POS),'call __mul_expr','push 3 call __bin_node','recurse','__mul_expr:','call __primary','call __mul_tail','return','__mul_tail:',f'{tok()} push 44 eq push 0 eq skiz return',inc(POS),'call __primary','push 4 call __bin_node','recurse']
    # Literal handler must consume token once, and signal completion separately.
    a += ['__primary:',put(TMP,0),f'{tok()} push 53 eq skiz call __literal_branch',f'{ld(TMP)} push 1 eq skiz return',f'{tok()} push 28 eq assert',inc(POS),'call __add_expr',f'{tok()} push 29 eq assert',inc(POS),'return']
    a += ['__literal_branch:',f'push 40 {node()} write_mem 1 pop 1',f'{tok(3)} {node(1)} write_mem 1 pop 1']
    for j in range(2,8): a += [f'push 0 {node(j)} write_mem 1 pop 1']
    a += [ld(ACOUNT),inc(ACOUNT),inc(POS),put(TMP,1),'return','__bin_node:',f'{node(1)} write_mem 1 pop 1',f'{node(3)} write_mem 1 pop 1',f'{node(2)} write_mem 1 pop 1',f'push 43 {node()} write_mem 1 pop 1']
    for j in range(4,8): a += [f'push 0 {node(j)} write_mem 1 pop 1']
    a += [ld(ACOUNT),inc(ACOUNT),'return','__parser_main:','call __read_source call __parse',f'{ld(ACOUNT)} write_io 1 push 0 write_io 1',put(POS,0),'call __ast_out','return','__ast_out:',f'{ld(POS)} {ld(ACOUNT)} eq skiz return']
    for j in range(8): a += [f'{ld(POS)} push 8 mul push {AST+j} add read_mem 1 pop 1 write_io 1']
    a += [inc(POS),'recurse']
    return '\n'.join(a)+'\n'

if __name__=='__main__':
    header='// Independent handwritten RAM algorithm; regenerate with scripts/generate_compiler_baselines.py.\n'
    (ROOT/'std/compiler/lexer.tasm').write_text(header+lexer())
    (ROOT/'std/compiler/parser.tasm').write_text(header+lexer()+parser())

def pipeline():
    a=['__pipeline_main:','call __read_source call __parse',f'{ld(ACOUNT)} write_io 1 push 0 write_io 1']
    for row in [[9,3,0,0],[7,3,0,0]]:
        a += [f'push {v} write_io 1' for v in row]
    a += [put(POS,4),'call __tir_expr']
    for row in [[2,0,0,0],[8,0,0,0]]:
        a += [f'push {v} write_io 1' for v in row]
    a += ['return','__tir_expr:',f'{ld(POS)} {ld(ACOUNT)} eq skiz return',f'{ld(POS)} push 8 mul push {AST} add read_mem 1 pop 1 push 40 eq skiz call __tir_literal',f'{ld(POS)} push 8 mul push {AST} add read_mem 1 pop 1 push 43 eq skiz call __tir_bin',inc(POS),'recurse','__tir_literal:','push 12 write_io 1',f'{ld(POS)} push 8 mul push {AST+1} add read_mem 1 pop 1 write_io 1','push 0 write_io 1 push 0 write_io 1 return','__tir_bin:',f'{ld(POS)} push 8 mul push {AST+1} add read_mem 1 pop 1 push 2 mul push 10 add write_io 1','push 0 write_io 1 push 0 write_io 1 push 0 write_io 1 return']
    return '\n'.join(a)+'\n'

def oracle(text):
    tokens=[]
    for m in re.finditer(r'\s+|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|->|.',text):
        word=m[0]
        if word.isspace(): continue
        if word in WORDS: k=WORDS.index(word)+1
        elif word.isdecimal(): k=53
        elif re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',word): k=54
        elif word=='->': k=39
        else: k=SYMBOLS[word]
        tokens.append([k,m.start(),m.end(),int(word) if k==53 else 0])
    tokens.append([56,len(text),len(text),0])
    nodes=[[1,1,1,1,0,1,1,0],[3,3,2,0,2,3,0,0],[10,0,0,0,0,0,0,0],[26,4,0,0,0,0,0,0]]
    pos=9
    def expr(min_bp=0):
        nonlocal pos
        t=tokens[pos];pos+=1
        if t[0]==53: lhs=len(nodes);nodes.append([40,t[3],0,0,0,0,0,0])
        elif t[0]==28:
            lhs=expr();assert tokens[pos][0]==29;pos+=1
        else: raise ValueError('expected expression')
        while tokens[pos][0] in [43,44]:
            op=tokens[pos][0];bp=6 if op==43 else 8
            if bp<min_bp: break
            pos+=1;rhs=expr(bp+1);n=len(nodes);nodes.append([43,3 if op==43 else 4,lhs,rhs,0,0,0,0]);lhs=n
        return lhs
    nodes[3][3]=expr();assert tokens[pos][0]==31
    tir=[[9,3,0,0],[7,3,0,0]]+[[12,n[1],0,0] if n[0]==40 else [16 if n[1]==3 else 18,0,0,0] for n in nodes[4:]]+[[2,0,0,0],[8,0,0,0]]
    return {'lexer':tokens,'parser':nodes,'pipeline':tir}

def driver(stage):
    imports='use vm.io.mem\nuse vm.core.convert\nuse std.compiler.lexer\n'
    read='let n = pub_read()\nassert(convert.as_u32(n) < convert.as_u32(1025))\nfor i in 0..n bounded 1024 { mem.write(1000 + convert.as_field(i), pub_read()) }\n'
    lex='lexer.lex(1000,n,2000,7000,7500)\nassert(mem.read(7502) == 0)\n'
    if stage=='lexer': call=lex;count='mem.read(7501)';base='2000';stride=4
    elif stage=='parser':
        imports+='use std.compiler.parser\n';call=lex+'parser.parse(2000,mem.read(7501),10000,18000,18500,19000)\nassert(mem.read(18503) == 0)\n';count='mem.read(18502)';base='10000';stride=8
    else:
        imports='use vm.io.mem\nuse vm.core.convert\nuse std.compiler.pipeline\n'
        call=''.join(f'mem.write(2000 + {k},{v})\n' for k,v in {0:1000,1:'n',4:1,5:5,6:10,7:3,8:16,9:1073741824,10:100000}.items())+'pipeline.compile(2000)\nassert(mem.read(2011) == 0)\n';count='mem.read(2003)';base='mem.read(2002)';stride=4
    writes='\n'.join(f'pub_write(mem.read(base + convert.as_field(i) * {stride} + {j}))' for j in range(stride))
    return f'program compiler_{stage}_fixture\n{imports}fn main() {{\n{read}{call}let count = {count}\nlet base = {base}\npub_write(count)\npub_write(0)\nfor i in 0..count bounded 1024 {{\n{writes}\n}}\n}}\n'

def fixtures():
    samples={'precedence':'program sample fn main() -> Field { 2 + 3 * 4 }','parentheses':'program another fn main() -> Field { (7 + 5) * (9 + 2) }','associativity':'program chain fn main() -> Field { 11 * 2 * 3 + 4 + 5 }'}
    for name,text in samples.items():
        expected=oracle(text)
        for stage,rows in expected.items():
            directory=ROOT/'fixtures'/f'compiler-{stage}-{name}';directory.mkdir(exist_ok=True)
            (directory/'main.tri').write_text(driver(stage))
            fields=[len(rows),0]+[v for r in rows for v in r]
            (directory/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/compiler/{stage}.tasm"\ntarget = "triton"\ninput = {[len(text),*text.encode()]}\noutput = {fields}\nmax_cycles = 500000\nreference = "Independent byte tokenization and Pratt AST/postfix TIR oracle; complete {stage} records; {name}. See std/compiler/README.md."\nhand_prefix = "call __{stage}_main halt"\n')
    for stage,label,text in [('lexer','reject','program bad @'),('parser','reject','program bad fn main() -> Field { 2 + }'),('pipeline','reject','program bad fn main() -> Field { 2 + }'),('pipeline','type-reject','program bad fn main() -> Field { true }')]:
        directory=ROOT/'fixtures'/f'compiler-{stage}-{label}';directory.mkdir(exist_ok=True)
        (directory/'main.tri').write_text(driver(stage))
        (directory/'vector.bench.toml').write_text(f'source = "main.tri"\nhand = "../../std/compiler/{stage}.tasm"\ntarget = "triton"\ninput = {[len(text),*text.encode()]}\noutput = []\nexpect_failure = true\nmax_cycles = 500000\nreference = "Malformed source must report an error; driver asserts zero errors. Hand reference rejects the invalid token/expression directly."\nhand_prefix = "call __{stage}_main halt"\n')

if __name__=='__main__':
    (ROOT/'std/compiler/pipeline.tasm').write_text(header+lexer()+parser()+pipeline())
    fixtures()
