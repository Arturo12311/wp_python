l = [0, 35, 192, 192, 148, 0, 64, 0, 0, 0, 52, 49, 67, 55, 66, 57, 54, 51, 65, 70, 70, 49, 53, 69, 52, 52, 66, 55, 48, 56, 54, 48, 56, 50, 49, 51, 54, 69, 65, 66, 51, 65, 68, 49, 50, 55, 65, 53, 49, 70, 54, 70, 50, 54, 66, 53, 70, 53, 56, 68, 56, 66, 49, 68, 51, 68, 56, 55, 66, 57, 53, 70, 66, 56, 0, 2, 0, 0, 0, 52, 53, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15]

print(len(l))

op = bytes([20, 158, 178, 142])
import struct

opcode = struct.unpack("<I", op)
print(opcode)

print(25 + (16 - (25 % 16)))
print(25 + 7)