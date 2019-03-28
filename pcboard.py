#!/cygdrive/c/Python27/python
#!/usr/local/bin/python2.7

import wx
import os
from sys import stdout
import subprocess
import re
import shutil
import platform
from time import localtime, strftime
from operator import attrgetter
from math import floor, hypot, sqrt

linux = platform.system() == 'Linux'

flipX = True
if flipX:
    flipAxis = 'X'
else:
    flipAxis = 'Y'

probing = True
probeGrid = 0.5
minPoints = 1
remove = False

drillDefaults = (("depth", "-0.095"),
                 ("retract", "0.030"),
                 ("safeZ", "1.000"),
                 ("feed", "7.0"),
                 ("change", "1.5"),
                 ("probeRetrct", "0.020"),
                 ("probeDepth", "-0.010"))

gDrawDefaults = (
    # ("v", ),
    # ("D", ),
    ("depth", "-0.0070"),
    ("retract", "0.020"),
    ("linearFeed", "14.0"),
    ("circularFeed", "14.0"))

if linux:
    gdraw = "/home/eric/java/GDraw.jar"
    drill = "/home/eric/java/Drill.jar"
    ncFiles = '/home/eric/linuxcnc/nc_files/'
    probeInput = '/home/eric/linuxcnc/configs/cncmill/'
else:
    gdraw = "c:\\development\\java\\gdraw\\dist\\GDraw.jar"
    drill = "c:\\development\\java\\drill\\dist\\Drill.jar"
    ncFiles = './'
    probeInput = './'

def removeFiles():
    global remove, linux, ncFiles, probeInput
    if remove & linux:
        rm = 'rm -f ' + ncFiles
        os.system(rm + '*.bmp')
        os.system(rm + '*.png')
        os.system(rm + '*.ngc')
        os.system(rm + '*~')
        os.system(rm + '*.dbg')
        os.system(rm + '*.prb')
        rm = 'rm -f ' + probeInput
        os.system(rm + '*.prb')

class Hole:
    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

def getHoles(fileName, xSize=0.0):
    try:
        f = open(fileName, "r")
    except IOError:
        return(None)
    holes = []
    tool = {}
    for l in f:
        l = l.strip()
        if l.startswith("%"):
            break
        m = re.search(r"^T(\d+)C(\d\.\d+)", l)
        if m != None:
            try:
                tool[int(m.group(1))] = float(m.group(2))
            except ValueError:
                pass

    # for size in tool:
    #     print(size)

    for l in f:
        l = l.strip()
        m = re.search(r"^T(\d+)", l)
        if m != None:
            try:
                # print(m.group(1))
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

        m = re.search(r"^X([\+-][\d]+)Y([\+-][\d]+)", l)
        if m != None:
            try:
                x = float(m.group(1)) / 10000.0
                y = float(m.group(2)) / 10000.0
            except ValueError:
                pass
            # print(x, y, size)
            if xSize != 0.0:
                x = xSize - x
            holes.append(Hole(x, y, size))
            continue
    
        if l == "M30":
            break
    f.close

    holes = sorted(holes, key=attrgetter('x', 'y'))
    # for hole in holes:
    #     print("x %7.4f y %7.4f %5.3f" % (hole.x, hole.y, hole.size))
    # print(len(holes))
    return(holes)

class MainFrame(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, -1, title)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.InitUI0()

    def onClose(self, event):
        self.Destroy()

    def InitUI0(self):
        panel = wx.Panel(self)

        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)

        btn = wx.Button(panel, label='File')
        btn.Bind(wx.EVT_BUTTON, self.OnSelect)
        sizerV.Add(btn, flag=wx.CENTER|wx.ALL, border=2)

        # select project

        self.projectName = txt = wx.StaticText(panel, -1, "Select Project")
        sizerV.Add(txt, flag=wx.CENTER|wx.ALL, border=2)

        self.boardSize = txt = wx.StaticText(panel, -1, "")
        sizerV.Add(txt, flag=wx.CENTER|wx.ALL, border=2)

        # measured board size and initial setup 

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        txt = wx.StaticText(panel, -1, "Board " + flipAxis + " Size")
        sizerH.Add(txt, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=2)

        self.yBox = tc = wx.TextCtrl(panel, -1, "", size=(60, -1))
        sizerH.Add(tc, flag=wx.ALL, border=2)

        btn = wx.Button(panel, label='Setup')
        btn.Bind(wx.EVT_BUTTON, self.OnSetup)
        sizerH.Add(btn, flag=wx.ALL, border=2)

        sizerV.Add(sizerH, flag=wx.CENTER|wx.ALL, border=2)

        # autolevel top

        if probing:
            sizerH = wx.BoxSizer(wx.HORIZONTAL)

            btn = wx.Button(panel, label='Level Top')
            btn.Bind(wx.EVT_BUTTON, self.OnLevelTop)
            sizerH.Add(btn, flag=wx.ALL, border=2)

            sizerV.Add(sizerH, flag=wx.CENTER|wx.ALL, border=2)

        # alignment hole and expected location

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        txt = wx.StaticText(panel, -1, "Hole " + flipAxis + " Location")
        sizerH.Add(txt, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=2)

        self.offsetBox = tc = wx.TextCtrl(panel, -1, "", size=(60, -1))
        tc.SetEditable(False)
        sizerH.Add(tc, flag=wx.ALL, border=2)

        sizerV.Add(sizerH, flag=wx.CENTER|wx.ALL, border=2)

        self.expLoc = txt = wx.StaticText(panel, -1, "")
        sizerV.Add(txt, flag=wx.ALL|wx.CENTER, border=2)

        # actual location and fix

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        txt = wx.StaticText(panel, -1, "Mill " + flipAxis + " Location")
        sizerH.Add(txt, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=2)

        self.inputBox = tc = wx.TextCtrl(panel, -1, "", size=(60, -1))
        sizerH.Add(tc, flag=wx.ALL, border=2)

        btn = wx.Button(panel, label='Fix')
        btn.Bind(wx.EVT_BUTTON, self.OnFix)
        sizerH.Add(btn, flag=wx.ALL, border=2)

        sizerV.Add(sizerH, flag=wx.CENTER|wx.ALL, border=2)

        # fix result line

        self.status = txt = wx.StaticText(panel, -1, "")
        sizerV.Add(txt, flag=wx.CENTER|wx.ALL, border=2)

        panel.SetSizer(sizerV)

        # autolevel bottom

        if probing:
            sizerH = wx.BoxSizer(wx.HORIZONTAL)

            btn = wx.Button(panel, label='Level Bottom')
            btn.Bind(wx.EVT_BUTTON, self.OnLevelBottom)
            sizerH.Add(btn, flag=wx.ALL, border=2)

            sizerV.Add(sizerH, flag=wx.CENTER|wx.ALL, border=2)

        self.sizerV.Fit(self)

        dw, _ = wx.DisplaySize()
        w, _ = self.GetSize()
        self.SetPosition((dw - w, 0))

        self.tmpPath = ""

    def getBoardSize(self, path):
        self.xSize = 0
        self.ySize = 0
        f = open(path, "r")
        for line in f:
            line = line.strip()
            print(line)
            m = re.match(r"^([XY])([\d]+)([XY]*)([\d]*)", line)
            if m != None:
                # print("(%s) (%s) (%s) (%s)" % \
                #       ( m.group(1), m.group(2), m.group(3), m.group(4)))
                # stdout.flush()
                for i in range(1, 4, 2):
                    if len(m.group(i)) != 0:
                        axis = m.group(i)
                        val = int(m.group(i + 1)) / 1000000.0
                        if axis == "X":
                            if val > self.xSize:
                                self.xSize = val
                        else:
                            if val > self.ySize:
                                self.ySize = val
        # print("xSize %7.4f ySize %7.4f" % (self.xSize, self.ySize))

    def OnSelect(self, e):
        self.dirname = ncFiles
        dlg = wx.FileDialog(self, "Choose a file", self.dirname,
                            "", "*.drl", wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            removeFiles()
            self.yBox.SetValue("")
            self.offsetBox.SetValue("")
            self.inputBox.SetValue("")
            self.status.SetLabel("")
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()

            self.path = os.path.join(self.dirname, self.filename)
            self.project = re.sub("\\.drl", "", self.filename)
            self.board = os.path.join(self.dirname, self.project + ".gbr")
            self.top = os.path.join(self.dirname, self.project + "_t.gbr")
            self.bottom = os.path.join(self.dirname, self.project + "_b.gbr")

            self.getBoardSize(self.board)
            self.boardSize.SetLabel("%6.3f x %6.3f" % \
                                    (self.xSize, self.ySize))
            self.yBox.SetValue("%0.3f" % \
                               (self.ySize, self.xSize)[flipX])
            
            tmp = probeGrid / 2.0
            self.xPoints = int(floor((self.xSize + tmp) / probeGrid))
            if self.xPoints == minPoints:
                self.xPoints += 1
            self.yPoints = int(floor((self.ySize + tmp) / probeGrid))
            if self.yPoints == minPoints:
                self.yPoints += 1
            if not probing:
                # self.probe('t')
                _ = self.drill(self.path)
            else:
                probeOptions = ["-p %d:%d -h" % (self.xPoints, self.yPoints), ]
                _ = self.drill(self.path, options=probeOptions)

            drill = self.project + "1.ngc"
            self.drillPath = os.path.join(self.dirname, drill)

            if not probing:
                self.gdraw(self.top, "")
                                          
            self.tmpPath = os.path.join(self.dirname, "tmp.ngc")

            dlg.Destroy()
            self.projectName.SetLabel(self.project)
            self.sizerV.Layout()

    def probe(self, side, boardX=0.0):
        probeFile = os.path.join(self.dirname,
                                 self.project + "_" + side + "p.ngc")
        drillFile = self.project + ".drl"
        holes = None
        if side == 'b':
            holes = getHoles(drillFile, boardX)
        self.xPoints = 6
        self.yPoints = 6
        margin = 0.125
        xStep = (self.xSize - 2 * margin) / (self.xPoints - 1)
        yStep = (self.ySize - 2 * margin) / (self.yPoints - 1)
        depth = -0.010
        retract = 0.020
        x = margin
        y0 = margin
        y1 = self.ySize - margin
        y = y0

        prb = open(probeFile, "w")
        t = strftime("%a %b %d %H:%M:%S %Y", localtime())
        prb.write("(%s %s)\n" % (probeFile, t))
        prb.write("(%6.4f %6.4f)\n" % (self.xSize, self.ySize))
        prb.write("(%d %d %6.4f %6.4f %6.4f)\n" % \
                  (self.xPoints, self.yPoints, margin, xStep, yStep))
        prb.write("g54	(coordinate system 2)\n")
        prb.write("g20	(units inches)\n")
        prb.write("g61	(exact path)\n")
        prb.write("f1.0 (probe feed rate)\n")
        prb.write("g0 z1.0\n")

        prb.write("g0 x%6.4f y%6.4f\n" % (x, y))
        prb.write("g0 z%6.4f\n\n" % (retract))
        prb.write("(PROBEOPEN %s_%s.prb)\n" % (self.project, side))
        fwd = True
        for i in range(self.xPoints):
            if fwd:
                y = y0
                j = 0
            else:
                y = y1
                j = self.yPoints - 1
            for _ in range(self.yPoints):
                if holes == None:
                    prb.write("g0 x%6.4f y%6.4f (%d %d x%6.4f y %6.4f)\n" % \
                              (x, y, i, j, x, y))
                else:
                    found = False
                    for (i0, hole) in enumerate(holes):
                        r = hole.size + 0.025
                        if hypot(hole.x - x, hole.y - y) < r:
                            dx = x - hole.x
                            dy = y - hole.y
                            print("%d %d %3d %6.4f %6.4f %6.4f %6.4f" % \
                                  (i, j, i0, x, y, hole.x, hole.y))
                            yOffset = sqrt(r * r - dx * dx)
                            if dy < 0:
                                yOffset = -yOffset
                            x0 = x
                            y0 = hole.y + yOffset
                            prb.write("g0 x%6.4f y%6.4f " \
                                      "(%d %d x%6.4f y%6.4f)\n" % \
                                      (x0, y0, i, j, x, y))
                            found = True
                            break
                    if not found:
                        prb.write("g0 x%6.4f y%6.4f (%d %d)\n" % \
                                  (x, y, i, j))
                prb.write("g38.2 z%6.4f\n" % (depth))
                prb.write("g0 z%6.4f\n\n" % (retract))
                if fwd:
                    y += yStep
                    j += 1
                else:
                    y -= yStep
                    j -= 1
            x += xStep
            fwd = not fwd
        prb.write("(PROBECLOSE %s.prb)\n" % (self.project))
        prb.write("g0 z1.5\n")
        prb.write("g0 x%5.3f y%5.3f\n" % (0.0, 0.0))
        prb.write("m2	(end of program)\n")
        prb.close()

    def OnLevelTop(self, e):
        fileName = self.project + "_t.prb"
        inputFile = os.path.join(probeInput, fileName)
        probeFile = os.path.join(self.dirname, fileName)
        if linux and not os.path.isfile(probeFile):
            try:
                shutil.move(inputFile, probeFile)
            except IOError:
                print("error connot find %s" % (inputFile))
                return
        _ = self.gdraw(self.top, "", "--probe=" + probeFile)

    def drillFix(self, drillPath, val):
        out = open(self.tmpPath, "w")
        fil = open(drillPath, "r")
        found = False
        for line in fil:
            if not found:
                m = re.match("#1.+?\\[(.+?) ", line)
                if m != None:
                    found = True
                    line = line[:m.start(1)] + val + line[m.end(1):]
            out.write(line)
        fil.close()
        out.close()
        os.unlink(self.drillPath)
        os.rename(self.tmpPath, self.drillPath)

    def OnSetup(self, e):
        val = self.yBox.GetValue()
        if len(val) != 0:
            self.measuredSize = float(val)
            self.drillFix(self.drillPath, val)

            fil = open(self.drillPath, "r")
            expr = "g0.+?" + flipAxis.lower() + "\\[.+? ([0-9\\.]+)\\]"
            for line in fil:
                m = re.match(expr, line)
                if m != None:
                    self.pos = float(m.group(1))
                    if flipX:
                        expLoc = self.measuredSize - self.pos
                    else:
                        expLoc = self.measuredSize - self.pos
                    self.expLoc.SetLabel('Exp ' + flipAxis + ' Loc %5.3f' %
                                         (expLoc))
                    self.offsetBox.SetValue('%5.3f' % (self.pos))
                    break
            fil.close()

            self.status.SetLabel("Size set to " + val)
            self.sizerV.Layout()

    def OnFix(self, e):
        val = self.inputBox.GetValue()
        if len(val) != 0:
            curPos = float(val)
            finalSize = curPos + self.pos
            delta = finalSize - self.measuredSize
            
            self.finalSize = "%5.3f" % finalSize
            self.drillFix(self.drillPath, self.finalSize)
            if probing:
                # self.probe('b', finalSize)
                probeOptions = ["-p %d:%d" % (self.xPoints, self.yPoints),
                                "-m x", # mirror x
                                "-h",   # use hole data
                                "-s b", # bottom
                                "-n"]   # no drill output
                self.drill(self.path, finalSize, probeOptions)
            else:
                self.gdraw(self.bottom, self.finalSize)
            if linux:
                nullDev = open("/dev/null", "w")
                subprocess.Popen(['/usr/bin/eog', ncFiles], stderr=nullDev)
            self.status.SetLabel("Size set to %5.3f diff %5.3f" %
                                 (finalSize, delta))
            self.sizerV.Layout()

    def OnLevelBottom(self, e):
        fileName = self.project + "_b.prb"
        probeFile = os.path.join(self.dirname, fileName)
        inputFile = os.path.join(probeInput, fileName)
        probeFile = os.path.join(self.dirname, fileName)
        if linux and not os.path.isfile(probeFile):
            try:
                shutil.move(inputFile, probeFile)
            except IOError:
                print("error connot find %s" % (inputFile))
                return
        _ = self.gdraw(self.bottom, self.finalSize, "--probe=" + probeFile)
        self.drillFix(self.drillPath, self.finalSize)
        if linux:
            nullDev = open("/dev/null", "w")
            subprocess.Popen(['/usr/bin/eog', ncFiles], stderr=nullDev)

    def drill(self, fileName, size=0.0, options=None):
        command = ["java", "-jar", drill]
        command.append("-" + flipAxis.lower())
        if size != 0.0:
            command.append("%5.3f" % (size))
        if options != None:
            command += options
        command.append(fileName)
        for d in drillDefaults:
            if len(d) == 2:
                command.append("--%s=%s" % d)
            else:
                command.append("-" + d[0])
        for str in command:
            print(str)
        stdout.flush()
        try:
            result = subprocess.check_output(command)
            print(result)
            stdout.flush()
            return(result)
        except subprocess.CalledProcessError as e:
            print("return code %d\n%s\n%s" % (e.returncode, e.cmd, e.output))
            return("")

        # if size == 0.0:
        #     result = subprocess.check_output(["java", "-jar", drill, axis,
        #                                       fileName])
        # else:
        #     result = subprocess.check_output(["java", "-jar", drill, axis,
        #                                       "%5.3f" % (size), fileName])
        # return result

    def gdraw(self, fileName, offset, probe=None):
        command = ["java", "-jar", gdraw]
        if len(offset) != 0:
            command.append("-" + flipAxis.lower())
            command.append(offset)
        if probe != None:
            command.append(probe)
        command.append(fileName)
        for d in gDrawDefaults:
            if len(d) == 2:
                command.append("--%s=%s" % d)
            else:
                command.append("-" + d[0])
        for str in command:
            print(str)
        stdout.flush()
        try:
            result = subprocess.check_output(command)
            print(result)
            stdout.flush()
            return(result)
        except subprocess.CalledProcessError as e:
            print("return code %d\n%s\n%s" % (e.returncode, e.cmd, e.output))
            return("")
    
        # if len(offset):
        #     if (len(offset) == 0):
        #         result = subprocess.check_output(["java", "-jar",
        #                                           gdraw,fileName])
        #     else:
        #         axis = '-' + flipAxis.lower()
        #         result = subprocess.check_output(["java", "-jar", gdraw, axis,
        #                                           offset,fileName])
        #     return result
        # else:
        #     result = subprocess.check_output(["java", "-jar", gdraw, fileName])
        #     return result

app = wx.App()

frame = MainFrame(None, 'PC Board')
frame.Show()

app.MainLoop()
