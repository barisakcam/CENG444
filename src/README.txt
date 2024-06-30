Short circuiting operations are not short circuited.
Functions can not return vectors.
Typing is not dynamic. For example you can not:
	var a = [1,2,3];
	a = 5;

To run:
	./vcc.sh <filename>

Multiple var declarations and undeclared vars are disabled. See vcc.py

Make sure vcc.py and vcc.sh has necessary permissions.

A dump file "dump.s" is created after compilation including asm code.