#!/usr/bin/env python3
"""Independent RAM-based Poseidon2 HL8 baseline, not compiler-generated assembly.
Constants: Plonky3 0835481398d2b481bef0c6d0e8188b484ab9a636 / p3-goldilocks 0.4.2.
Scratch RAM [2000000,2000016) is overwritten. Inputs/outputs: lane0 deepest.
"""
from pathlib import Path
EXTERNAL = [15949291268843349465, 14644164809401934923, 18420360874837380316, 4756469047455716334, 8685499049481102115, 3799221349720045367, 13676397835037157930, 6566439050423619635, 17428268347612331188, 2833135872454503769, 4767009016213040191, 2797635963551733652, 5312339450141126694, 5356668452102813289, 1234059326449530173, 7724302552453704877, 14868588146468890290, 12825281145595371185, 13097885453579304196, 7905326782341128063, 14167525334039893569, 2082169701994688927, 12190787523818595537, 12602917751946636, 14890907856876319003, 16552240149997473409, 5634093690795187558, 4883714163685656967, 12440776365164557866, 3923800234666204307, 9858064884105950259, 16040043470428402038, 94277733998400326, 10891359798487446420, 18280773820738154043, 13714589910668449566, 10639034072771185213, 14148790895768484219, 18341268649720100165, 3096672942770686236, 12277596046563557393, 400461754528604020, 12955488253560265444, 11773677676764285572, 4833837465239476573, 17645852643693996619, 6605134696140007471, 588040525114200273, 11001741536026769411, 17917086578469406776, 14893530806420712543, 727997185253761138, 3443873847340254325, 13095911531247069692, 8330737046680948619, 6014364575875986011, 16851679856681761121, 17817965496543149594, 12823640325246269760, 13685256787930775147, 4682652317564502291, 4233879762155685988, 11097258179564187322, 10804761421745472094]
INTERNAL = [5226594323142090582, 1243120476974621208, 12100812801659301173, 11228203327983058121, 13891617888374767564, 5742893160230537107, 3763472116988983643, 2466655769425769160, 6254574254498162968, 14183251225809189357, 11565357354521717084, 17300657704266685688, 310485250821938281, 16853586468012618118, 1978800426240373849, 6948188224235462572, 1486402152218690509, 5669161690283398991, 17943970877073781734, 17926851897715769433, 13052837496695000666, 18138113741095562305]
DIAG = [12216033376705242021, 2072934925475504800, 16432743296706583078, 1287600597097751715, 10482065724875379356, 3057917794534811537, 4460508886913832365, 4574242228824269566]
M4 = [[5,7,1,3],[4,6,1,1],[1,3,5,7],[1,1,4,6]]
BASE = 2000000
code = ["// Poseidon2 HL8, upstream constants pinned in scripts/generate_poseidon_baseline.py",
        "// Scratch RAM [2000000,2000016); hashN returns explicitly truncated lane0."]
def emit(s): code.append(s)
def read(i): return f"push {BASE+i} read_mem 1 pop 1"
def write(i): return f"push {BASE+i} write_mem 1 pop 1"
for n in range(1,5):
    for digest in (False, True):
        name = f"hash{n}" + ("_digest" if digest else "")
        emit(f"std_crypto_poseidon__{name}: call __{name} return")
        emit(f"__{name}:")
        for i in reversed(range(n)): emit(write(i))
        for i in range(n,8): emit(f"push {n if i==4 else 0} " + write(i))
        emit("call __poseidon_ram")
        for i in range(4 if digest else 1): emit(read(i))
        emit("return")
emit("std_crypto_poseidon__permute: call __permute return")
emit("__permute:")
for i in reversed(range(8)): emit(write(i))
emit("call __poseidon_ram")
for i in range(8): emit(read(i))
emit("return")
emit("__poseidon_sbox: dup 0 dup 0 mul dup 1 mul dup 0 mul mul return")
emit("__poseidon_external:")
for block in (0,4):
    for row in range(4):
        terms=[read(block+j)+f" push {M4[row][j]} mul" for j in range(4)]
        emit(terms[0]+" "+" ".join(t+" add" for t in terms[1:])+" "+write(8+block+row))
for i in range(8): emit(read(8+i)+" "+read(8+i%4)+" add "+read(12+i%4)+" add "+write(i))
emit("return")
emit("__poseidon_internal:")
emit(read(0)+" "+" ".join(read(i)+" add" for i in range(1,8)))
for i,d in enumerate(DIAG): emit("dup 0 "+read(i)+f" push {d} mul add "+write(i))
emit("pop 1 return")
emit("__poseidon_ram: call __poseidon_external")
for round in range(30):
    if 4 <= round < 26:
        emit(read(0)+f" push {INTERNAL[round-4]} add call __poseidon_sbox "+write(0))
        emit("call __poseidon_internal")
    else:
        r = round if round<4 else round-22
        for i in range(8): emit(read(i)+f" push {EXTERNAL[r*8+i]} add call __poseidon_sbox "+write(i))
        emit("call __poseidon_external")
emit("return")
root=Path(__file__).resolve().parents[1]
(root / "baselines/triton/std/crypto/poseidon.tasm").write_text("\n".join(code)+"\n")
