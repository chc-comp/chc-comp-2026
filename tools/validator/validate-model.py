#!/usr/bin/env python3
import smtlib
import sys

chc_file = sys.argv[1]
assert chc_file.endswith(".smt2")

smt_file = chc_file[:-4] + "-validate.smt2"

funs = {}


def define_funs(cmds, funs):
    for cmd in cmds:
        match cmd:
            case ("define-fun", name, *args):
                funs[name] = cmd


if True:
    file = sys.stdin
    for line in file:
        if line.strip() == "sat":
            break
    else:
        raise ValueError("No line with 'sat' found")
    content = file.read()
    model = smtlib.parse_exprs(content)

    match model:
        # SMT-LIB standard
        case [("model", *cmds)]:
            define_funs(cmds, funs)
        # Eldarica
        case [("define-fun", *_), *_] as cmds:
            define_funs(cmds, funs)
        # Z3
        case [cmds]:
            define_funs(cmds, funs)

with open(chc_file, "r") as file:
    content = file.read()
    cmds = smtlib.parse_exprs(content)

defs = []
clauses = []

for cmd in cmds:
    match cmd:
        case ("set-logic", "HORN"):
            defs.append(("set-logic", "ALL"))

        case ("set-option", ":produce-models", "true"):
            pass

        case ("declare-fun", name, *args):
            defs.append(funs[name])

        case ("assert", phi):
            clauses.append(phi)

        case ("check-sat",):
            pass
        case ("get-model",):
            pass
        case ("exit",):
            pass

        case _:
            defs.append(cmd)

for cmd in defs:
    for line in smtlib.print_expr_non_recursive(cmd):
        print(line)

goal = ("assert", ("not", ("and", *clauses)))

for line in smtlib.print_expr(goal):
    print(line)

print("(set-info :status unsat)")
print("(check-sat)")
