#!/usr/bin/env bash

CC="riscv64-unknown-linux-gnu-gcc"
CFLAGS="-march=rv64gcv -static"
STRIP_DIR=${1#*/}

./vcc.py ${1}
${CC} ${CFLAGS} dump.s print.c -o ${STRIP_DIR%.*}