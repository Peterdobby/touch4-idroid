.syntax unified
.arm
.global _start
.text

_start:
    mov r0, #1              @ stdout, inherited from the kernel console
    adr r1, message
    movw r2, #:lower16:message_length
    mov r7, #4              @ write
    svc #0

wait:
    mov r7, #29             @ pause
    svc #0
    b wait                  @ PID 1 must stay alive

message:
    .ascii "N81: Linux userspace is running\n"
.equ message_length, . - message
