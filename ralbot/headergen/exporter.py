import os
import enum
import textwrap
from typing import Tuple
from datetime import datetime

from systemrdl.node import AddressableNode, RootNode
from systemrdl.node import AddrmapNode, MemNode
from systemrdl.node import RegNode, RegfileNode, FieldNode
from systemrdl import rdltypes

# ===============================================================================
class headerGenExporter:
    def __init__(self, **kwargs):

        self.headerFileContent = list()

        # Check for stray kwargs
        if kwargs:
            raise TypeError(
                "got an unexpected keyword argument '%s'" % list(kwargs.keys())[0]
            )

        self.definePrefix = "#"

        self.line_len = 75
        self.doc_line_prefix = " * "

        self.baseAddressName = ""
        self.filename = ""
        self.dirname = "."
        self.define = self.definePrefix + "define "
        self.ifnDef = self.definePrefix + "ifndef "
        self.ifDef = self.definePrefix + "ifdef "
        self.endIf = self.definePrefix + "endif"
        self.generated_enums = []
        self.generated_structs = []

    # ---------------------------------------------------------------------------
    def export(self, node, path):
        # Make sure output directory structure exists
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.dirname = os.path.split(path)[0]
        filename = os.path.basename(path)
        filename = os.path.splitext(filename)[0]
        self.filename = filename + ".h"

        # Add header comment
        file_cmt = "\nWARNING: AUTOGENERATED FILE. DO NOT MODIFY.\n"
        file_cmt += (
            "Created: " + datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ") + "\n"
        )
        # file_cmt += "From: " +
        self.headerFileContent.append(self.create_docblock(file_cmt))

        # Add top of include guard now.
        includeGuard = self.filename
        includeGuard = includeGuard.upper().replace(".", "_")
        self.includeGuard = includeGuard.upper().replace("-", "_")
        self.headerFileContent.append("{:s}{:s}".format(self.ifnDef, self.includeGuard))
        self.headerFileContent.append(
            "{:s}{:s}\n".format(self.define, self.includeGuard)
        )

        self.headerFileContent.append(
            "#ifdef  __cplusplus\n" 'extern "C"\n' "{\n" "#endif\n"
        )
        self.headerFileContent.append("#include <stdint.h>\n")

        # If it is the root node, skip to top addrmap
        if isinstance(node, RootNode):
            node = node.top

        if not isinstance(node, AddrmapNode):
            raise TypeError(
                "'node' argument expects type AddrmapNode. Got '%s'"
                % type(node).__name__
            )

        # Determine if top-level node should be exploded across multiple
        # addressBlock groups
        explode = False

        if isinstance(node, AddrmapNode):
            addrblockable_children = 0
            non_addrblockable_children = 0

            for child in node.children(unroll=False):
                if not isinstance(child, AddressableNode):
                    continue

                if isinstance(child, (AddrmapNode, MemNode)) and not child.is_array:
                    addrblockable_children += 1
                else:
                    non_addrblockable_children += 1

            if (non_addrblockable_children == 0) and (addrblockable_children >= 1):
                explode = True

        # Do the export!
        if explode:
            # top-node becomes the memoryMap
            # Top-node's children become their own addressBlocks
            for child in node.children(unroll=True):
                if not isinstance(child, AddressableNode):
                    continue
                self.add_addressBlock(child)
        else:
            # Not exploding apart the top-level node
            # Wrap it in a dummy memoryMap that bears it's name
            # Export top-level node as a single addressBlock
            self.add_addressBlock(node)

        self.headerFileContent.append("\n#ifdef  __cplusplus\n" "}\n" "#endif\n")

        # "endif" include block
        self.headerFileContent.append(
            "\n{:s} /* {:s} */\n".format(self.endIf, self.includeGuard)
        )
        # Write out UVM RegModel file
        with open(os.path.join(self.dirname, self.filename), "w") as f:
            f.write("\n".join(self.headerFileContent))

    # ---------------------------------------------------------------------------
    def add_def(self, content):
        self.headerFileContent.append(self.define + content)

    # ---------------------------------------------------------------------------
    def add_addressBlock(self, node):
        self.add_docblock(node)
        self.add_def("%s 0" % ("%s_BASE_ADDR" % node.inst_name.upper()))
        self.baseAddressName = "%s_BASE_ADDR" % node.inst_name.upper()

        for child in node.children():
            print(type(child), child)

            if isinstance(child, RegNode):
                self.add_register(parent=node, node=child)
            elif isinstance(child, (AddrmapNode, RegfileNode)):
                self.add_docblock(node=child)
                self.add_regfile_struct(regfile_node=child)
                # self.add_registerFile(node=child)

    # def add_registerFile(self, node):
    #     for child in node.children():
    #         if isinstance(child, RegNode):
    #             self.add_register(parent=node, node=child)
    #         elif isinstance(child, (AddrmapNode, RegfileNode)):
    #             self.add_docblock(node=child)
    #             self.add_registerFile(node=child)

    # ---------------------------------------------------------------------------
    def add_register(self, parent, node):
        macro_var_name = "n"

        if parent.is_array:
            self.add_def(
                "{:s}_{:s}({:s}) ({:s} + {:#x} + ({:s}*{:#x}) + {:#x})".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    macro_var_name,
                    self.baseAddressName,
                    parent.raw_address_offset,
                    macro_var_name,
                    parent.array_stride,
                    node.address_offset,
                )
            )
        elif node.is_array:
            self.add_def(
                "{:s}_{:s}_INST_MAX {}".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    node.array_dimensions[0],
                )
            )
            self.add_def(
                "{:s}_{:s}({:s}) ({:s} + {:#x} + ({:s}*{:#x}))".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    macro_var_name,
                    self.baseAddressName,
                    node.raw_address_offset,
                    macro_var_name,
                    node.array_stride,
                )
            )
        else:
            self.add_def(
                "{:s}_{:s} ({:s} + {:#x})".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    self.baseAddressName,
                    node.absolute_address,
                )
            )

        reg_rst_val = 0
        # Add register field position and mask defines
        for field in node.fields():
            self.check_write_field_typedef(field)
            self.add_def_field_pos_mask(
                parent.inst_name.upper() + "_" + node.inst_name.upper(), field
            )
            reg_rst_val |= field.get_property("reset", default=0) << field.low

        self.headerFileContent.append(
            "/** Reset value of '{}' */".format(node.inst_name)
        )
        self.add_def(
            "{:s}_{:s}_RESET {:#x}".format(
                parent.inst_name.upper(), node.inst_name.upper(), reg_rst_val
            )
        )

    def add_docblock(self, node):
        txt = node.get_property("name").replace("\n", " ").replace("\r", "") + "\n\n"

        desc = node.get_property("desc")
        if desc is not None:
            desc = desc.replace("\n", " ").replace("\r", "")
            desc += "\n\n"
        else:
            desc = ""
            # desc = "[No description]\n\n"

        desc += "[SystemRDL path: '" + node.get_path() + "']"

        txt += desc
        self.headerFileContent.append(self.create_docblock(txt))

    def add_inline_desc(self, node):
        if node.get_html_desc() is not None:
            desc = node.get_property("desc").strip()
            desc = desc.replace("\n", " ").replace("\r", "")

            access_desc = ""
            if node.get_property("sw"):
                access_desc = node.get_property("sw").name.upper() + ","

            onrd_desc = ""
            if node.get_property("onread"):
                onrd_desc = node.get_property("onread").name.upper() + ","

            onwr_desc = ""
            if node.get_property("onwrite"):
                onwr_desc = node.get_property("onwrite").name.upper() + ","

            self.headerFileContent.append(
                "/** {:s}, {}{}{} */".format(
                    desc,
                    access_desc,
                    onrd_desc,
                    onwr_desc,
                )
            )

    def create_docblock(self, txt: str) -> str:
        "Wrap text and prepend asterisks to create a Doxygen-like doc block"

        lines = txt.splitlines()
        reflowed = lines[0]
        for i in range(1, len(lines)):
            reflowed += (
                "\n"
                + self.doc_line_prefix
                + textwrap.fill(lines[i], subsequent_indent=self.doc_line_prefix)
            )
        return "\n/** {}\n */".format(reflowed)

    def check_write_field_typedef(self, field):
        fencode = field.get_property("encode")

        if isinstance(fencode, enum.Enum):
            print("is (builtin) enum.Enum")
            return
        elif rdltypes.is_user_enum(fencode):
            self.add_enum(fencode)

    def add_enum(self, user_enum):
        enum_id = "{}::{}".format(user_enum.get_scope_path(), user_enum.__name__)

        if enum_id in self.generated_enums:
            return
        self.generated_enums.append(enum_id)
        print("Adding enum:", enum_id)

        txt = user_enum.__name__.replace("\n", " ").replace("\r", "") + "\n\n"
        txt += "[SystemRDL path: '" + enum_id + "']"
        self.headerFileContent.append(self.create_docblock(txt))

        self.headerFileContent.append(
            "typedef enum " + user_enum.__name__.upper() + "_e {"
        )
        for e in user_enum:
            self.headerFileContent.append(
                "  /** {} */\n  {:s} = {:d},".format(
                    e.rdl_desc,
                    user_enum.__name__.upper() + "_" + e.name.upper(),
                    int(e),
                )
            )
            # self.add_inline_desc(e)

        self.headerFileContent.append("} " + user_enum.__name__.upper() + "_t;\n")

    def add_regfile_struct(self, regfile_node):
        self.headerFileContent.append("typedef struct __attribute__((packed)) {")

        for reg in regfile_node.children():
            self.add_reg_fields_union(reg_node=reg)

        self.headerFileContent.append("}} {}_t;\n".format(regfile_node.inst_name))

    def add_reg_fields_union(self, reg_node):

        nofields_reg = ""
        field_cnt = 0
        field_strs = []
        for field in reg_node.fields():
            field_cnt += 1

            ftype, fbits = self.get_c_field_type(field_node=field)
            s = ftype + " "
            s += field.inst_name
            if fbits is not None:
                s += fbits
            s += ";"

            field_strs.append(s)

            nofields_reg = ftype + " " + reg_node.inst_name
            if fbits is not None:
                nofields_reg += fbits
            nofields_reg += ";"

        if field_cnt > 1:
            self.headerFileContent.append("struct {")
            self.headerFileContent.extend(field_strs)
            self.headerFileContent.append("} " + reg_node.inst_name + ";")
        else:
            self.headerFileContent.append(nofields_reg)

    def get_c_field_type(self, field_node) -> Tuple[str, str]:
        c_type = "UNSUPPORTED_STD_C_TYPE"
        # SystemRDL 2.0 section 6.2.1 says all types are unsigned
        if field_node.width <= 8:
            c_type = "uint8_t"
        elif field_node.width <= 16:
            c_type = "uint16_t"
        elif field_node.width <= 32:
            c_type = "uint32_t"
        elif field_node.width <= 64:
            c_type = "uint64_t"

        bitfield_str = None

        if ((field_node.width % 4) != 0) or (field_node.width < 8):
            bitfield_str = ":{:d}".format(field_node.width)

        return (c_type, bitfield_str)

    # ---------------------------------------------------------------------------
    def add_def_field_pos_mask(self, parent_name: str, field_node):

        # FIXME: Not sure that I like this, after running a few example files
        # through this exporter. Thinking that instead documentation for fields
        # should be added to a register's doc block. Would probably look cleaner.
        self.add_inline_desc(field_node)

        # maskValue = int("1" * field_node.width, 2) << field_node.low
        # self.add_def("{:s}_Msk {:#x}U".format(field_name, maskValue))
        maskValue = field_node.width
        field_name = "{:s}_{:s}".format(parent_name, field_node.inst_name.upper())

        self.add_def("{:s}_Msk (0x{:X}U << {}U)".format(field_name, maskValue, field_node.low))

       
        self.add_def("{:s}_Pos {:d}U".format(field_name, field_node.low))



        # encode = field_node.get_property("encode")
        # if encode is not None:
        #    for enum_value in encode:
        #        print("debug point enum ", enum_value.name, enum_value.rdl_name, enum_value.rdl_desc)
        #        print("debug point ", "enum value", "'h%x" % enum_value.value)
