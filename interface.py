import popen2
import select
import os
import signal
import time
import fcntl

try:
    import gtkinterface
    frontend = gtkinterface.Interface()
except:
    import terminalinterface
    frontend = terminalinterface.Interface()

def _makeNonBlocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
        
def execute(command):
    return_code = -1
    process = popen2.Popen3(command, True)
    
    _makeNonBlocking(process.fromchild)
    _makeNonBlocking(process.childerr)
    
    build_paused = False
    
    while (return_code == -1):
        # Allow the frontend to get a little time
        frontend.runEventLoop()

        #If there's data on the command's stdout, read it
        selection = select.select([process.fromchild], [], [], 0)
        if (selection[0] != []):
            frontend.printToBuildOutput(process.fromchild.read())

        selection = select.select([process.childerr], [], [], 0)
        if (selection[0] != []):
            frontend.printToWarningOutput(process.childerr.read())
                
                    
        # See if we should pause the current command
        if ((build_paused == False) and (frontend.pauseBuild() == True)):
            os.kill(process.pid, signal.SIGSTOP)
            build_paused = True
        elif ((build_paused == True) and (frontend.pauseBuild() == False)):
            os.kill(process.pid, signal.SIGCONT)
            build_paused = False
        elif (build_paused == False):
            return_code = process.poll()

        time.sleep(0.05)

    # Read any remaining output lines    
    value = process.fromchild.read()
    while (value != ""):
        frontend.printToBuildOutput(value)
        value = process.fromchild.read()

    # Read any remaining stderr lines
    value = process.childerr.read()
    while (value != ""):
        frontend.printToWarningOutput(value)
        value = process.childerr.read()
        
    return return_code
