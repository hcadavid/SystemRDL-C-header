import os
import textwrap

from systemrdl.node import AddressableNode, RootNode
from systemrdl.node import AddrmapNode, MemNode
from systemrdl.node import RegNode, RegfileNode, FieldNode

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
        self.hexPrefix = "0x"

        self.line_len = 75
        self.doc_line_prefix = " * "

        self.baseAddressName = ""
        self.filename = ""
        self.dirname = "."
        self.define = self.definePrefix + "define "
        self.ifnDef = self.definePrefix + "ifndef "
        self.ifDef = self.definePrefix + "ifdef "
        self.endIf = self.definePrefix + "endif"

    # ---------------------------------------------------------------------------
    def export(self, node, path):
        # Make sure output directory structure exists
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.dirname = os.path.split(path)[0]
        filename = os.path.basename(path)
        filename = os.path.splitext(filename)[0]
        self.filename = filename + ".h"

        # Add top of include guard now.
        includeGuard = self.filename
        includeGuard = includeGuard.upper().replace(".", "_")
        self.includeGuard = includeGuard.upper().replace("-", "_")
        self.headerFileContent.append("{:s}{:s}".format(self.ifnDef, self.includeGuard))
        self.headerFileContent.append(
            "{:s}{:s}\n".format(self.define, self.includeGuard)
        )

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
            if isinstance(child, RegNode):
                self.add_register(node, child)
            elif isinstance(child, (AddrmapNode, RegfileNode)):
                self.add_registerFile(child)

    def add_registerFile(self, node):
        for child in node.children():
            if isinstance(child, RegNode):
                self.add_register(node, child)
            elif isinstance(child, (AddrmapNode, RegfileNode)):
                self.add_docblock(child)
                self.add_registerFile(child)

    # ---------------------------------------------------------------------------
    def add_register(self, parent, node):
        macro_var_name = "BASE"
        self.add_docblock(node)
        if parent.is_array:
            self.add_def(
                "{:s}_{:s}({:s}) ({:s} + {:s}{:x} + {:s}*{:s}{:x} + {:s}{:x})".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    macro_var_name,
                    self.baseAddressName,
                    self.hexPrefix,
                    parent.raw_address_offset,
                    macro_var_name,
                    self.hexPrefix,
                    parent.array_stride,
                    self.hexPrefix,
                    node.address_offset,
                )
            )
        elif node.is_array:
            self.add_def(
                "{:s}_{:s}({:s}) ({:s} + {:s}{:x} + {:s}*{:s}{:x})".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    macro_var_name,
                    self.baseAddressName,
                    self.hexPrefix,
                    node.raw_address_offset,
                    macro_var_name,
                    self.hexPrefix,
                    node.array_stride,
                )
            )
        else:
            self.add_def(
                "{:s}_{:s} ({:s} + {:s}{:x})".format(
                    parent.inst_name.upper(),
                    node.inst_name.upper(),
                    self.baseAddressName,
                    self.hexPrefix,
                    node.absolute_address,
                )
            )

        for field in node.fields():
            self.add_field(node, field)

    def add_docblock(self, node):
        txt = node.get_property("name").replace("\n", " ").replace("\r", "")

        desc = node.get_property("desc")
        if desc is None:
            desc = "[No description]"
        desc = desc.replace("\n", " ").replace("\r", "")
        desc += "\n\n" + node.get_path()

        txt += "\n\n" + desc
        lines = txt.splitlines()

        reflowed = ""
        for l in lines:
            reflowed += (

                textwrap.fill(l, subsequent_indent=self.doc_line_prefix)
                + "\n" +  self.doc_line_prefix
            )

        self.headerFileContent.append("\n/** {}\n */".format(reflowed))

    def add_inline_desc(self, node):
        if node.get_html_desc() is not None:
            self.headerFileContent[-1] += " /**< {:s} */".format(
                node.get_property("desc")
            )

    # ---------------------------------------------------------------------------
    def add_field(self, parent, node):

        field_name = "{:s}_REG_{:s}".format(
            parent.inst_name.upper(), node.inst_name.upper()
        )
        self.add_def("{:s}_OFFSET {:d}U".format(field_name, node.low))

        maskValue = int("1" * node.width, 2) << node.low
        self.add_def("{:s}_MASK 0x{:X}U".format(field_name, maskValue))
        self.add_inline_desc(node)

        # encode = node.get_property("encode")
        # if encode is not None:
        #    for enum_value in encode:
        #        print("debug point enum ", enum_value.name, enum_value.rdl_name, enum_value.rdl_desc)
        #        print("debug point ", "enum value", "'h%x" % enum_value.value)
