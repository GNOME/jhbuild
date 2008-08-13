
import commands

def jhbuild_list(c, moduleset, modules):
    command = c['jhbuild'] + " --file="+ c['jhbuildrc'] +" --moduleset=" + moduleset + " " + "list" + " " + modules
    (status, output) = commands.getstatusoutput(command)
    if (status == 0):
        return [x for x in output.split('\n') if x[:5] != "meta-"]
    return []
