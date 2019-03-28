#!/usr/bin/python2.7

from __future__ import print_function
from math import floor, hypot
import re
from operator import attrgetter

class Hole:
    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

holes = []
tool = {}
fileName = "OutputM2.drl"
f = open(fileName, "r")
for l in f:
    l = l.strip()
    if l.startswith("%"):
        break
    m = re.search("^T(\d+)C(\d\.\d+)", l)
    if m != None:
        try:
            tool[int(m.group(1))] = float(m.group(2))
        except ValueError:
            pass

for size in tool:
    print(size)

for l in f:
    l = l.strip()
    m = re.search("^T(\d+)", l)
    if m != None:
        try:
            print(m.group(1))
            ap = int(m.group(1))
        except ValueError:
            pass
        try:
            if ap in tool:
                size = tool[ap]
            else:
                size = 0.0
        except IndexError:
            pass
        continue

    m = re.search("^X([\+-][\d]+)Y([\+-][\d]+)", l)
    if m != None:
        try:
            x = float(m.group(1)) / 10000.0
            y = float(m.group(1)) / 10000.0
        except ValueError:
            pass
        print(x, y, size)
        holes.append(Hole(x, y, size))
        continue
    
    if l == "M30":
        break
f.close

holes = sorted(holes, key=attrgetter('x', 'y'))

print(len(holes))
for hole in holes:
    print("x %7.4f y %7.4f %5.3f" % (hole.x, hole.y, hole.size))
