#!/usr/bin/env python3

import sys
import os

# Ignore this. Only needed for this example
this_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(this_dir, "../"))


from systemrdl import RDLCompiler, RDLCompileError
from ralbot.headergen import headerGenExporter

# Collect input files from the command line arguments
input_file = sys.argv[1]
input_file_basename = os.path.splitext(input_file)[0]

# Create an instance of the compiler
rdlc = RDLCompiler()

try:
    # Compile the file provided
    rdlc.compile_file(input_file)

    # Elaborate the design
    root = rdlc.elaborate()
except RDLCompileError:
    # A compilation error occurred. Exit with error code
    sys.exit(1)

fname_out = os.path.abspath(os.path.join("./out", input_file_basename))
print("Generating:", fname_out)
headerfile = headerGenExporter()
headerfile.export(root, fname_out)
