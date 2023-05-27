import json
from pathlib import Path
from typing import IO, cast, Optional, Union

from blockdefs import reporters, statements
from sb3 import Block, Costume, Input, MutatedBlock, Sprite

INFIX = {
    "operator_and": "and",
    "operator_or": "or",
    "operator_equals": "=",
    "operator_gt": ">",
    "operator_lt": "<",
    "operator_add": "+",
    "operator_subtract": "-",
    "operator_multiply": "*",
    "operator_divide": "/",
    "operator_join": "&",
}
INFIX_PRECEDENCE = list(INFIX.values())


def name(name: str) -> str:
    w = "".join(
        i
        for i in "".join(i.capitalize() for i in name.split(" ")).lower()
        if i.isidentifier()
    )
    try:
        return w[0].lower() + w[1:]
    except:
        return "idk"


def string(o: str) -> str:
    return '"' + repr(o)[1:-1] + '"'


def literal(o: str) -> str:
    try:
        return str(int(o))
    except ValueError:
        try:
            return str(float(o))
        except ValueError:
            return string(o)


class CodeGen:
    def __init__(
        self, out: IO[str], sprite: Sprite, globals: list[str], listglobals: list[str]
    ) -> None:
        self.out = out
        self.indent: int = 0
        self.sprite = sprite
        self.blocks = sprite["blocks"]
        if globals:
            self.tabwrite("globals " + ", ".join(map(name, globals)) + ";\n")
        if listglobals:
            self.tabwrite("listglobals " + ", ".join(map(name, listglobals)) + ";\n")
        self.costumes(self.sprite["costumes"])
        for block in self.blocks.values():
            if type(block) == list:
                continue
            if block["topLevel"]:
                self.block(block)

    def write(self, o: str) -> None:
        self.out.write(o)

    def tabwrite(self, o: str) -> None:
        self.write("  " * self.indent + o)

    def costumes(self, costumes: list[Costume]) -> None:
        self.tabwrite("costumes")
        if costumes:
            self.write(" ")
        last, costumes = costumes[-1:], costumes[:-1]

        def f(costume: Costume):
            self.write(string(costume["name"] + Path(costume["md5ext"]).suffix))

        for costume in costumes:
            f(costume)
            self.write(", ")
        if last:
            f(last[0])
        self.write(";\n\n")

    def getblockfrominput(self, o: Input) -> Optional[Block]:
        if o[0] in (1, 2, 3) and isinstance(o[1], str):
            block: str = o[1]
            return self.blocks[block]

    def input(self, o: Input, parens: bool = False) -> None:
        # BLOCK
        if o[1] is None:
            return
        if o[0] in (1, 2, 3) and isinstance(o[1], str):
            block: str = o[1]
            self.block(self.blocks[block], parens)
        # STRING LITERAL
        elif o[0] == 1 and o[1][0] in (4, 5, 6, 7, 8, 10, 11):
            string: str = o[1][1]
            self.write(literal(string))
        # VARIABLE REPORTER
        elif o[0] == 3 and o[1][0] == 12:
            variable: str = o[1][1]
            self.write(name(variable))

    def infix(self, o: Block, op: str, parens: bool) -> None:
        def f(a: int) -> None:
            if a >= len(list(o["inputs"].keys())):
                return
            input = o["inputs"][list(o["inputs"].keys())[a]]
            block = self.getblockfrominput(input)
            if (
                block
                and block["opcode"] in INFIX
                and INFIX_PRECEDENCE.index(op)
                > INFIX_PRECEDENCE.index(INFIX[block["opcode"]])
            ):
                self.block(block, True)
            else:
                self.input(input)

        if parens:
            self.write("(")
        f(0)
        self.write(" " + op + " ")
        f(1)
        if parens:
            self.write(")")

    def block(self, o: Union[Block, MutatedBlock], parens: bool = False) -> None:
        if o["opcode"] == "argument_reporter_string_number":
            self.argument(o)
        elif o["opcode"] in INFIX:
            self.infix(o, INFIX[o["opcode"]], parens)
        elif o["opcode"] == "looks_costume":
            self.input([1, [4, o["fields"]["COSTUME"][0]]])
        elif o["opcode"] == "looks_backdrops":
            self.input([1, [4, o["fields"]["BACKDROP"][0]]])
        elif o["opcode"] == "sound_sounds_menu":
            self.input([1, [4, o["fields"]["SOUND_MENU"][0]]])
        elif o["opcode"] == "sensing_keyoptions":
            self.input([1, [4, o["fields"]["KEY_OPTION"][0]]])
        elif o["opcode"] == "procedures_definition":
            self.define(o)
        elif o["opcode"] == "procedures_call":
            self.call(cast(MutatedBlock, o))
        elif o["opcode"] == "event_whenbroadcastreceived":
            self.broadcast(o)
        elif o["opcode"] == "control_if":
            self.control_if(o)
        elif o["opcode"] == "control_if_else":
            self.control_if_else(o)
        elif o["opcode"] == "control_repeat_until":
            self.control_repeat_until(o)
        elif o["opcode"] == "control_repeat":
            self.control_repeat(o)
        elif o["opcode"] == "control_forever":
            self.control_forever(o)
        elif o["opcode"] == "data_setvariableto":
            self.data_setvariableto(o)
        elif o["opcode"] == "data_changevariableby":
            self.data_changevariableby(o)
        elif o["opcode"] == "data_deletealloflist":
            self.data_deletealloflist(o)
        elif o["opcode"] == "data_addtolist":
            self.data_additemtolist(o)
        elif o["opcode"] == "data_deleteoflist":
            self.data_deleteitemoflist(o)
        elif o["opcode"] == "data_insertatlist":
            self.listinsert(o)
        elif o["opcode"] == "data_replaceitemoflist":
            self.listreplace(o)
        elif o["opcode"] == "data_showlist":
            self.listshow(o)
        elif o["opcode"] == "data_hidelist":
            self.listhide(o)
        elif o["opcode"] == "data_itemoflist":
            self.itemoflist(o)
        elif o["opcode"] == "data_itemnumoflist":
            self.listindex(o)
        elif o["opcode"] == "data_lengthoflist":
            self.listlength(o)
        elif o["opcode"] == "data_listcontainsitem":
            self.listcontains(o)
        elif o["opcode"] == "event_whenflagclicked":
            self.onflag(o)
        elif o["opcode"] == "event_whenthisspriteclicked":
            self.onclick(o)
        elif o["opcode"] == "control_start_as_clone":
            self.onclone(o)
        elif o["opcode"] == "event_whenbroadcastreceived":
            self.on(o)
        elif o["opcode"] == "event_whenkeypressed":
            self.onkey(o)
        elif o["opcode"] == "event_whenbackdropswitchesto":
            self.onbackdrop(o)
        elif (
            o["opcode"] == "event_whengreaterthan"
            and o["fields"]["WHENGREATERTHANMENU"][0] == "LOUDNESS"
        ):
            self.onloudness(o)
        elif (
            o["opcode"] == "event_whengreaterthan"
            and o["fields"]["WHENGREATERTHANMENU"][0] == "TIMER"
        ):
            self.ontimer(o)
        else:
            opcode = self.getopcode(statements, o)
            if opcode:
                return self.statement(opcode, o)
            opcode = self.getopcode(reporters, o)
            if opcode:
                return self.reporter(opcode, o)

    def onflag(self, o: Block) -> None:
        self.tabwrite("onflag")
        self.stack(o)

    def onclone(self, o: Block) -> None:
        self.tabwrite("onclone")
        self.stack(o)

    def onclick(self, o: Block) -> None:
        self.tabwrite("onclone")
        self.stack(o)

    def onkey(self, o: Block) -> None:
        self.tabwrite("onkey ")
        self.write(string(o["fields"]["KEY_OPTION"][0]))
        self.stack(o)

    def onbackdrop(self, o: Block) -> None:
        self.tabwrite("onbackdrop ")
        self.write(string(o["fields"]["BACKDROP_OPTION"][0]))
        self.stack(o)

    def onloudness(self, o: Block) -> None:
        self.tabwrite("onloudness ")
        self.input(o["inputs"]["VALUE"])
        self.stack(o)

    def ontimer(self, o: Block) -> None:
        self.tabwrite("ontimer ")
        self.input(o["inputs"]["VALUE"])
        self.stack(o)

    def on(self, o: Block) -> None:
        self.tabwrite("on ")
        self.write(string(o["fields"]["BROADCAST_OPTION"][0]))
        self.stack(o)

    def stack(self, o: Block) -> None:
        self.write(" {\n")
        self.indent += 1
        self.next(o)
        self.indent -= 1
        self.tabwrite("}\n\n")

    def statement(self, opcode: str, o: Block) -> None:
        self.tabwrite(opcode)
        if o["inputs"]:
            self.write(" ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)

    def next(self, o: Block) -> None:
        if o["next"]:
            self.block(self.blocks[o["next"]])

    def reporter(self, opcode: str, o: Block) -> None:
        self.write(opcode + "(")
        self.blockinputs(o)
        self.write(")")

    def argument(self, o: Block) -> None:
        self.write("$" + name(o["fields"]["VALUE"][0]))

    def blockinputs(self, o: Block) -> None:
        inputs = list(o["inputs"].values())
        last, inputs = inputs[-1:], inputs[:-1]
        for input in inputs:
            self.input(input)
            self.write(", ")
        if last:
            self.input(last[0])

    def control_if(self, o: Block) -> None:
        self.tabwrite("if ")
        self.input(o["inputs"]["CONDITION"])
        self.write(" {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK"][1]])
        self.indent -= 1
        self.tabwrite("}\n")
        self.next(o)

    def control_repeat(self, o: Block) -> None:
        self.tabwrite("repeat ")
        self.input(o["inputs"]["TIMES"])
        self.write(" {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK"][1]])
        self.indent -= 1
        self.tabwrite("}\n")
        self.next(o)

    def control_forever(self, o: Block) -> None:
        self.tabwrite("forever {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK"][1]])
        self.indent -= 1
        self.tabwrite("}\n")
        self.next(o)

    def control_repeat_until(self, o: Block) -> None:
        self.tabwrite("until ")
        self.input(o["inputs"]["CONDITION"])
        self.write(" {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK"][1]])
        self.indent -= 1
        self.tabwrite("}\n")
        self.next(o)

    def control_if_else(self, o: Block) -> None:
        self.tabwrite("if ")
        self.input(o["inputs"]["CONDITION"])
        self.write(" {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK"][1]])
        self.indent -= 1
        self.tabwrite("} else {\n")
        self.indent += 1
        if o["inputs"]["SUBSTACK2"][1]:
            self.block(self.blocks[o["inputs"]["SUBSTACK2"][1]])
        self.indent -= 1
        self.tabwrite("}\n")
        self.next(o)

    def getopcode(self, opcodes: dict[str, str], block: Block) -> Optional[str]:
        if block["inputs"]:
            for name, value in block["inputs"].items():
                if value[0] == 1 and isinstance(value[1], str) and name in self.blocks[value[1]]["fields"]:
                    opcode = (
                        block["opcode"]
                        + "!"
                        + (name + "=" + self.blocks[value[1]]["fields"][name][0])
                    )
                    try:
                        return opcodes[opcode]
                    except KeyError:
                        pass
        if block["fields"]:
            for name, value in block["fields"].items():
                opcode = block["opcode"] + "." + (name + "=" + value[0])
                try:
                    return opcodes[opcode]
                except KeyError:
                    pass
        return opcodes.get(block["opcode"])

    def data_setvariableto(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["VARIABLE"][0]) + " = ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)

    def data_changevariableby(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["VARIABLE"][0]) + " += ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)

    def data_deletealloflist(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + "[];\n")
        self.next(o)

    def listshow(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + ".show;\n")
        self.next(o)

    def listhide(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + ".hide;\n")
        self.next(o)

    def data_additemtolist(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + ".add ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)

    def data_deleteitemoflist(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + ".delete ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)

    def itemoflist(self, o: Block) -> None:
        self.write(name(o["fields"]["LIST"][0]) + "[")
        self.blockinputs(o)
        self.write("]")

    def listindex(self, o: Block) -> None:
        self.write(name(o["fields"]["LIST"][0]) + ".index(")
        self.blockinputs(o)
        self.write(")")

    def listcontains(self, o: Block) -> None:
        self.write(name(o["fields"]["LIST"][0]) + ".contains(")
        self.blockinputs(o)
        self.write(")")

    def listlength(self, o: Block) -> None:
        self.write(name(o["fields"]["LIST"][0]) + ".length")

    def listinsert(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + ".insert ")
        self.input(o["inputs"]["INDEX"])
        self.write(", ")
        self.input(o["inputs"]["ITEM"])
        self.write(";\n")
        self.next(o)

    def listreplace(self, o: Block) -> None:
        self.tabwrite(name(o["fields"]["LIST"][0]) + "[")
        self.input(o["inputs"]["INDEX"])
        self.write("] = ")
        self.input(o["inputs"]["ITEM"])
        self.write(";\n")
        self.next(o)

    def define(self, o: Block) -> None:
        prototype = cast(MutatedBlock, self.blocks[o["inputs"]["custom_block"][1]])
        if not json.loads(prototype["mutation"]["warp"]):
            self.tabwrite("nowarp def ")
        else:
            self.tabwrite("def ")
        self.write(name(prototype["mutation"]["proccode"].split("%")[0]) + " ")
        self.write(", ".join(json.loads(prototype["mutation"]["argumentnames"])))
        self.write(" {\n")
        self.indent += 1
        self.next(o)
        self.indent -= 1
        self.tabwrite("}\n\n")

    def broadcast(self, o: Block) -> None:
        self.tabwrite("on ")
        self.write(string(o["fields"]["BROADCAST_OPTION"][0]))
        self.write(" {\n")
        self.indent += 1
        self.next(o)
        self.indent -= 1
        self.write("}\n\n")

    def call(self, o: MutatedBlock) -> None:
        self.tabwrite(name(o["mutation"]["proccode"].split("%")[0]))
        if o["inputs"]:
            self.write(" ")
        self.blockinputs(o)
        self.write(";\n")
        self.next(o)
