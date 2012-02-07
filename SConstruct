# This file is part of xrayutilities.
#
# xrayutilities is free software; you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published by 
# the Free Software Foundation; either version 2 of the License, or 
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2009 Eugen Wintersberger <eugen.wintersberger@desy.de>
# Copyright (C) 2010-2012 Dominik Kriegner <dominik.kriegner@aol.at>

import os
import datetime
import subprocess

AddOption("--prefix",dest="prefix",type="string",
          default="/usr/local",metavar="INSTALL_ROOT",
          action="store",nargs=1)

AddOption("DESTDIR", 'Destination root directory', '')

env = Environment(PREFIX=GetOption("prefix"),ENV=os.environ,
                  DESTDIR=GetOption("DESTDIR"),
                  CCFLAGS=["-fPIC","-Wall","-std=c99"],
                  tools = ["default", "disttar"], toolpath=[os.path.join(".","tools")])
                  
                  #CCFLAGS=["-fPIC","-Wall","-pthread"],
                  #LIBS=["m","pthread"])

# package xrayutilities into a tarball for distribution
#print("Creating tarball for redistribution of xrayutilities...")
env['DISTTAR_FORMAT']='gz'
env.Append(
    DISTTAR_EXCLUDEEXTS=['.o','.os','.so','.a','.dll','.dylib','.cache','.dblite','.pyc','.log','.out','.aux','.fls','.toc'], 
    DISTTAR_EXCLUDEDIRS=['.svn','.sconf_temp', 'dist', 'build'],
    DISTTAR_EXCLUDERES=[r'clib_path.conf'])

env.DistTar(os.path.join("dist","xrayutilities_"+datetime.date.today().isoformat()), [env.Dir(".")]) 

if "install" in COMMAND_LINE_TARGETS:
    #write the clib_path.conf file
    print("create clib_path.conf file")
    conffilename = os.path.join(".","python","xrutils","clib_path.conf")
    fid = open(conffilename,"w")
    pref = env['DESTDIR'] + env['PREFIX']
    if os.sys.platform == "darwin":
        libpath = os.path.join(pref,"lib","libxrutils.dylib")
    elif os.sys.platform == "linux2":
        libpath = os.path.join(pref,"lib","libxrutils.so")
    elif "win" in os.sys.platform:
        libpath = os.path.join(pref,"lib","xrutils.dll")
    fid.write("[xrutils]\n")
    fid.write("clib_path = %s\n" %libpath)
    fid.close()
    #run python installer
    python_installer = subprocess.Popen("python setup.py install --home="+pref,shell=True)
    python_installer.wait()

############################
#    config like things
############################

def CheckPKGConfig(context, version):
    context.Message( 'Checking for pkg-config... ' )
    ret = context.TryAction('pkg-config --atleast-pkgconfig-version=%s' % version)[0]
    context.Result( ret )
    return ret

def CheckPKG(context, name):
    context.Message( 'Checking for %s... ' % name )
    ret = context.TryAction('pkg-config --exists \'%s\'' % name)[0]
    context.Result( ret )
    return ret

# check for headers, libraries and packages
if not env.GetOption('clean'):

    conf = Configure(env,custom_tests = { 'CheckPKGConfig' : CheckPKGConfig, 'CheckPKG' : CheckPKG })
    if not conf.CheckCC():
        print('Your compiler and/or environment is not correctly configured.')
        Exit(1)
    
    #if not conf.CheckPKGConfig('0.20.0'):
    #    print 'pkg-config >= 0.20.0 not found.'
    #    Exit(1)
 
    #if not conf.CheckPKG('cblas'):
    #    print 'cblas not found.'
    #    Exit(1)

    if not conf.CheckHeader(['stdlib.h','stdio.h','math.h','time.h']):
        print 'Error: did not find one of the needed headers!'
        Exit(1)
   
    if not conf.CheckLibWithHeader('gomp','omp.h','c'):
        print 'Warning: did not find openmp + header files -> using serial code'
    else:
        env.Append(CCFLAGS=['-fopenmp','-D__OPENMP__'],LIBS=['gomp'])

    if not conf.CheckLibWithHeader('pthread','pthread.h','c'):
        print 'Error: did not find pthread + header files!'
    else:
        env.Append(CCFLAGS=['-pthread'],LIBS=['pthread'])

    if not conf.CheckLib(['m']):
        print 'Error: did not find one of the needed libraries!'
        Exit(1)

    conf.Finish()

#env.ParseConfig('pkg-config --cflags --libs cblas')

#add the aliases for install target
env.Alias("install",["$PREFIX/lib"])#,"$PREFIX/bin"])

#add aliases for documentation target
env.Alias("doc",["doc/manual/xrutils.pdf"])

debug = ARGUMENTS.get('debug', 0)
if int(debug):
    env.Append(CCFLAGS=["-g","-O0"])
else:
    env.Append(CCFLAGS=["-O2"])

Export("env")

#add subdirectories
SConscript(["src/SConscript","doc/manual/SConscript"])
