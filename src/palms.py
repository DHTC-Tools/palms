#!/usr/bin/python
# __author__ = 'marco'
"""
v0 of PALMS
Package is available in some relocatable tarball format
PALMS uses tha package (file or URL), dovnloads it if needed and installs it in the correct place
Then it updates a database of installed applications
Flag to accept a new keyword
Structure:
APP_ROOT - app - app_plt_ver (one for each install) [rename, if 2 or more mkdir+move]
               - plt - ver (mult)
                     - default
               - plt (different) - ver (mult)
                                 - default
               - $ARCH (link to the correct architecture - used only in setup)
         - _etc (database)
warning if the version already exists
palms -i (--install) name arch ver URL
    -f force install
    -d default version
    -n accept new keyword
    --syncdb
    -s --setup
    -r (--remove)
"""


import os
import sys
import tarfile

# keywords
PREFIX="PALMS_"
ANY="%sANY" % PREFIX
NOT_SPECIFIED="%sNA" % PREFIX
#DEFAULT="%sDEFAULT" % PREFIX
DEFAULT="default"

# directory structure
# software tree
SW_DIR = "sw"
REPO_DIR = "repo"
SHARE_DIR = "share"
BCK_DIR = "bck"

# imports for findversion
import sys
import os
import platform
import optparse

class FindVersion (object):
    UNKNOWN="UNKNOWN"
    UNSUPPORTED="UNSUPPORTED"
    RH5="el5"
    RH6="el6"
    OSX="mac"
    OSX_UNSUPPORTED="mac" #"UNSUPPORTED"
    DEB6="deb6"

    SUPPORTED_OSX = ['10.6', '10.7', '10.8']
    SUPPORTED_PLATFORMS = [ RH5, RH6, OSX, DEB6 ]

    BIT32="i386" #"32bit"
    BIT64="x86_64" #"64bit"

    def __init__(self):
        pass

    def findversion_mac(self, detail=False):
        # system_profiler -detailLevel mini SPSoftwareDataType | grep "System Version"
        #      System Version: Mac OS X 10.6.8 (10K549)
        # #
        import commands
        ec, out = commands.getstatusoutput('system_profiler -detailLevel mini SPSoftwareDataType | grep "System Version"')
        retv = out.strip()[len("System Version:"):].strip()
        if detail and ec==0:
            return retv
        if retv.startswith('Mac OS X 10.'):
            version = [i.strip() for i in retv.strip()[len("Mac OS X "):].split('.')]
            if '.'.join(version[:2]) in self.SUPPORTED_OSX:
                return self.OSX
            return self.OSX_UNSUPPORTED
        return self.UNKNOWN

    def findversion_redhat(self, detail=False):
    # content of /etc/redhat-release
    #Scientific Linux release 6.2 (Carbon)
    #Red Hat Enterprise Linux Server release 5.8 (Tikanga)
    #Scientific Linux SL release 5.5 (Boron)
    #CentOS release 4.2 (Final)
    #
    #Do we support FC:Fedora Core release 11 ... ?
    #
    # should I check that it is SL/RHEL/CentOS ?
    # no
        lines = open('/etc/redhat-release').readlines()
        for line in lines:
            if detail and 'release'in line:
                return line
            if 'release 5.' in line:
                return self.RH5
            if 'release 6.' in line:
                return self.RH6
            return self.UNSUPPORTED
        return self.UNKNOWN

    def findversion_debian(self, detail=False):
        """cat /etc/*release
DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=11.10
DISTRIB_CODENAME=oneiric
DISTRIB_DESCRIPTION="Ubuntu 11.10"

user@bellatrix:~$ lsb_release
No LSB modules are available.

user@bellatrix:~$ lsb_release -a
No LSB modules are available.

Distributor ID:    Ubuntu
Description:    Ubuntu 11.10
Release:    11.10
Codename:    oneiric
        """
        retv=self.UNSUPPORTED
        lines = open('/etc/lsb-release').readlines()
        for line in lines:
            if detail:
                if 'DISTRIB_DESCRIPTION' in line:
                    return line[len('DISTRIB_DESCRIPTION='):]
            if 'DISTRIB_ID' in line:
                if not 'Debian' in line:
                    return self.UNSUPPORTED
            if 'DISTRIB_RELEASE' in line:
                if line[len('DISTRIB_RELEASE='):].startswith('6.'):
                    retv=self.DEB6
        return retv

    def findversion(self):
        if not os.name=='posix':
            return self.UNSUPPORTED
        if sys.platform=='darwin':
            myver = platform.mac_ver()
            if myver[0]:
                if '.'.join(myver[0].split('.')[:2]) in self.SUPPORTED_OSX:
                    return self.OSX
            return self.findversion_mac()
        elif sys.platform.startswith('linux'):
            # only 64 bit supported
            #if not platform.architecture()[0]=='64bit':
            #     return UNSUPPORTED
            # try first platform.dist, use it only for positive recognition
            mydist = platform.dist()
            if mydist[0]:
                if mydist[0].lower()=='redhat':
                    if mydist[1].startswith('5.'):
                        return self.RH5
                    if mydist[1].startswith('6.'):
                        return self.RH6
                if mydist[0].lower()=='debian':
                    if mydist[1].startswith('6.'):
                        return self.DEB6
            if os.path.isfile('/etc/redhat-release'):
                return self.findversion_redhat()
            elif os.path.isfile('/etc/lsb-release'):
                return self.findversion_debian()
        return self.UNKNOWN

    def findversion_detail(self):
        #if not os.name=='posix':
        #  return UNKNOWN
        if sys.platform=='darwin':
            return self.findversion_mac(True)
        elif sys.platform.startswith('linux'):
            if os.path.isfile('/etc/redhat-release'):
                return self.findversion_redhat(True)
        elif os.path.isfile('/etc/lsb-release'):
            return self.findversion_debian(True)
        return self.UNKNOWN

    def find_system(self):
        ret = self.findversion()
        if ret == self.UNKNOWN or ret == self.UNSUPPORTED:
            return None
        return ret

    def find_arch(self):
        if platform.architecture()[0]=='64bit':
            return "x86_64"
        return "i386"

class Package (object):
    tarball_file = None
    tarball_url = None
    name = None
    architecture = None
    system = None
    version = None

    def __init__(self, name, system=None, architecture=None, version=None):
        self.name = name
        self.architecture = architecture
        self.system = system
        self.version = version

    def set_from_name(self, name_path):
        """Use the name (file path or URL) to set all the attributes
        Format: name(may contain -)-system-architecture-version(no - allowed)[.tar.gz|.tgz|.tar]
        """
        appname = os.path.basename(name_path)
        parts = appname.rsplit('-', 3)
        self.name = parts[0]
        self.system = parts[1]
        self.architecture = parts[2]

        #m.lower().endswith(('.png', '.jpg', '.jpeg'))
        #ext = os.path.splitext(fp)[-1].lower()


    def set_tarball_file(self, tarball_path):
        self.tarball_file = tarball_path

    def set_tarball_url(self):
        pass

    def make_install_pathname(self):
        """
        Path used for the install directory. Uses generic names if nothing is specified
        """
        system = self.system
        if not system:
            system = ANY
        arch = self.architecture
        if not arch:
            arch = ANY
        version = self.version
        if not version:
            version = NOT_SPECIFIED
        rets = os.path.join(self.name, system, arch, version)
        return rets

    def make_setup_pathname(self):
        """ Path used by palms setup command, uses defults according to current system
        """
        curr = FindVersion()
        system = self.system
        if not system:
            system = curr.find_system()
        arch = self.architecture
        if not arch:
            arch = curr.find_arch()
        version = self.version
        if not version:
            version = DEFAULT
        rets = os.path.join(self.name, system, arch, version)
        return rets

    def make_repo_pathname(self):
        """
        Path of the sw repository
        """
        system = self.system
        if not system:
            system = ANY
        arch = self.architecture
        if not arch:
            arch = ANY
        version = self.version
        if not version:
            version = NOT_SPECIFIED
        rets = "%s-%s-%s-%s" % (self.name, system, arch, version)
        return rets


    def __str__(self):
        rets = "Sw: %s (%s, %s, %s)" % (self.name, self.system, self.architecture,
                                        self.version)



class PlatformMgr (object):
    #systems_list = ['RHEL5', 'RHEL6']
    systems_list = ['el5', 'el6']
    arch_dictionary = { 'el5': ['x86_64', 'i386'],
                        'el6': ['x86_64', 'i386'],
                        NOT_SPECIFIED: [],
                        ANY: [],
                        }
    manager = None
    def __init__(self):
        pass

    def getMgr(cls):
        if cls.manager:
            return cls.manager
        cls.manager = cls()
        return cls.manager
    getMgr = classmethod(getMgr)

    def list_systems(self):
        return self.systems_list

    def list_architectures(self, system):
        #if not system in self.systems_list:
        if not system in self.arch_dictionary.keys():
            return []
        return self.arch_dictionary[system]


class Palms (object):
    DEFAULT_ROOT_DIR = "/cvmfs/oasis.opensciencegrid.org/osg/palms"
    DEFALUT_VERSION = DEFAULT #'default'
    UP_INSTALL_DIR = os.path.join('..','..','..','..') #'../../../..' # make_install_pathname
    EXCLUDED_DIR = ['ARCH', 'DIST', 'PLATFORM']
    EXCLUDED_PREFIX = ['JUMP']
    EXCLUDED_SUFFIX = ['jump']
    root_dir = None
    rel_install_root_dir = None
    rel_repo_root_dir = None
    rel_bck_root_dir = None
    rel_share_root_dir = None
    shell = None
    #install_root_dir = None
    #repo_root_dir = None
    bck_root_dir = None

    def __init__(self, root_dir='.', write=False):
        self.rel_install_root_dir = SW_DIR
        self.rel_repo_root_dir = REPO_DIR
        self.rel_share_root_dir = SHARE_DIR
        self.rel_bck_root_dir = BCK_DIR
        self.root_dir = root_dir
        # TODO: make root_dir and repo/inst/bck roots if not existing (or raise exception)
        # all methods can assume oot dir
        if not os.path.isdir(root_dir):
            raise OSError("Palms root dir does not exist: %s" % root_dir)
        if write:
            if not os.path.exists(self.get_repo_root_dir()):
                os.mkdir(self.get_repo_root_dir())
            if not os.path.exists(self.get_install_root_dir()):
                os.mkdir(self.get_install_root_dir())
            if not os.path.exists(self.get_share_root_dir()):
                os.mkdir(self.get_share_root_dir())
            if not os.path.exists(self.get_bck_root_dir()):
                os.mkdir(self.get_bck_root_dir())

    def set_shell(self, shell_type):
        if shell_type in ['csh', 'tcsh', 'cshe']:
            shell_type = 'csh'
        else:
            shell_type = 'sh'
        self.shell = shell_type

    def get_shell(self):
        return self.shell

    def get_install_root_dir(self):
        return os.path.abspath(os.path.join(self.root_dir, self.rel_install_root_dir))

    def get_repo_root_dir(self):
        return os.path.abspath(os.path.join(self.root_dir, self.rel_repo_root_dir))

    def get_share_root_dir(self):
        return os.path.abspath(os.path.join(self.root_dir, self.rel_share_root_dir))

    def get_bck_root_dir(self):
        return os.path.abspath(os.path.join(self.root_dir, self.rel_bck_root_dir))

    def make_dir_old(self, name, platform, version, default=False):
        # should it check if the whole path exists? or assume it does not?
        this_root = os.path.join(self.root_dir, name)
        new_dir = False
        if not os.path.isdir(this_root):
            new_dir = True
            os.mkdir(this_root)
        this_dir = os.path.join(this_root, platform)
        if new_dir or not os.path.isdir(this_dir):
            new_dir = True
            os.mkdir(this_dir)
            default = True
        this_root = this_dir
        this_dir = os.path.join(this_root, version)
        if not new_dir and os.path.isdir(this_dir):
            return None
        os.mkdir(this_dir)
        if default:
            # make a link (relative path)
            os.symlink(version, os.path.join(this_root, Palms.DEFAULT_VERSION))
        return this_dir

    def make_dir(root_dir, rel_path, default=False, default_name=DEFAULT):
        # TODO: fix?
        version = ""
        # should it check if the whole path exists? or assume it does not?
        if not os.path.isdir(root_dir):
            # Fail, no rood dir
            pass
        this_dir = root_dir
        new_dir = False
        for path_element in os.path.split(rel_path):
            this_root = this_dir
            this_dir = os.path.join(this_root, path_element)
            if not os.path.isdir(this_dir):
                new_dir = True
                os.mkdir(this_dir)
        if new_dir or default:
            os.symlink(path_element, os.path.join(this_root, default_name))
            if not os.path.isdir(this_dir):
                pass
            new_dir = True
            os.mkdir(this_dir)
            default = True
        this_root = this_dir
        this_dir = os.path.join(this_root, version)
        if not new_dir and os.path.isdir(this_dir):
            return None
        os.mkdir(this_dir)
        if default:
            # make a link (relative path)
            os.symlink(version, os.path.join(this_root, Palms.DEFAULT_VERSION))
        return this_dir
    make_dir = staticmethod(make_dir)

    def is_not_specified(path):
        if not path or path == NOT_SPECIFIED:
            return True
        return False
    is_not_specified = staticmethod(is_not_specified)

    def is_any(path):
        if not path or path == ANY:
            return True
        return False
    is_any = staticmethod(is_any)

    def remove_install_link(self, package, repo_rel_dir, default_name=DEFAULT):
        cur_path = os.path.join(self.get_install_root_dir(), package.name, package.system, package.architecture, package.version)


    def make_install_link(self, package, repo_rel_dir, is_default=False, default_name=DEFAULT):
        # name - system - arch - version
        new_path = False
        mgr = PlatformMgr.getMgr()
        # All directories could be directories or links (aliases)
        name_path = os.path.join(self.get_install_root_dir(), package.name)
        if not os.path.exists(name_path):
            new_path = True
            os.mkdir(name_path)
        system = package.system
        if not system:
            system = ANY
        sys_path = os.path.join(name_path, system)
        if new_path or not os.path.exists(sys_path):
            new_path = True
            os.mkdir(sys_path)
            if Palms.is_any(system):
                for i in mgr.list_systems():
                    os.symlink(system, os.path.join(name_path,i))
        arch = package.architecture
        if not arch:
            arch = ANY
        arch_path = os.path.join(sys_path, arch)
        if new_path or not os.path.exists(arch_path):
            new_path = True
            is_default = True
            os.mkdir(arch_path)
            if Palms.is_any(arch):
                for i in mgr.list_architectures(system):
                    os.symlink(arch, os.path.join(sys_path,i))
        version = package.version
        if not version:
            version = NOT_SPECIFIED
        ver_path = os.path.join(arch_path, version)
        #print "Making a link %s <- %s" % (os.path.join(Palms.UP_INSTALL_DIR, repo_rel_dir), ver_path)
        if new_path or not os.path.exists(ver_path):
            new_path = True
            # make the link
            os.symlink(os.path.join(Palms.UP_INSTALL_DIR, repo_rel_dir), ver_path)
            #os.mkdir(ver_path)
        # if it is requested as default or the architecture was created or is the only one
        if is_default or len(os.listdir(arch_path))==1:
            default_path = os.path.join(arch_path, default_name)
            if os.path.exists(default_path):
                os.remove(default_path)
            os.symlink(version, default_path)
        if new_path:
            return ver_path
        return None


    def remote_install(self):
        # using ssh to the OASIS server
        pass

    # TODO: move this to Package
    def make_install_pathname(package):
        system = package.system
        if not system:
            system = ANY
        arch = package.architecture
        if not arch:
            arch = ANY
        version = package.version
        if not version:
            version = NOT_SPECIFIED
        rets = os.path.join(package.name, system, arch, version)
        return rets
    make_install_pathname = staticmethod(make_install_pathname)


    # TODO: move this to Package
    def make_repo_pathname(package):
        system = package.system
        if not system:
            system = ANY
        arch = package.architecture
        if not arch:
            arch = ANY
        version = package.version
        if not version:
            version = NOT_SPECIFIED
        rets = "%s-%s-%s-%s" % (package.name, system, arch, version)
        return rets
    make_repo_pathname = staticmethod(make_repo_pathname)

    def install(self, package, force=False, update=False, default=False, empty_ok=False, no_link=False):
        # If already installed, then fail if not force
        # installation is done in repo_root_dir
        # link for access in install_root_dir
        # need both update and force?
        if not force and self.is_conflicting(package):
            # TODO: manage exceptions (logging + handling)
            print "Package conflicting with existing installations"
            return None
        instdir = os.path.join(self.get_repo_root_dir(), Palms.make_repo_pathname(package))
        if os.path.exists(instdir):
            if not force:
                # Stopped install because already installed
                return None
        else:
            if update:
                # Trying to update not installed package. Raise exception? Check yum
                update = False
            os.mkdir(instdir)
        inst_tarball = None
        if package.tarball_file:
            inst_tarball = package.tarball_file
        else:
            # download and assign
            pass

        # open and extract the tar file
        if inst_tarball or empty_ok:
            tfile = tarfile.open(inst_tarball)

            if tarfile.is_tarfile(inst_tarball):
                # list all contents
                #print "tar file contents:"
                #print tfile.list(verbose=False)
                # extract all contents
                tfile.extractall(instdir)
            else:
                # Raise the error?
                print inst_tarball + " is not a tarfile."
        # create link in install tree
        if not no_link:
            self.make_install_link(package, os.path.join(self.rel_repo_root_dir, Palms.make_repo_pathname(package)),
                               default)
        return instdir


    def is_installed(self, package):
        instdir = os.path.join(self.get_install_root_dir(), package.make_setup_pathname())
        if os.path.exists(instdir):
            return True
        # Try also install pathname?
        instdir = os.path.join(self.get_install_root_dir(), package.make_install_pathname())
        if os.path.exists(instdir):
            return True
        return False

    def is_conflicting(self, package):
        # Def of conflicting:
        # same name +
        #  either system NOT_DEFINED or same system +
        #   either architecture NOT_DEFINED
        tmp_dir = os.path.join(self.get_repo_root_dir(), package.name)
        if not os.path.exists(tmp_dir):
            return False
        if not package.system or os.path.exists(os.path.join(tmp_dir, ANY)):
            return True
        tmp_dir = os.path.join(tmp_dir, package.system)
        if not os.path.exists(tmp_dir):
            return False
        if not package.architecture or os.path.exists(os.path.join(tmp_dir, ANY)):
            return True
        return False


    def get_setup(self, package):
        # return self.get_setup_int(package.name, package.system, package.architecture, package.version)
        return os.path.join(self.get_install_root_dir(), package.make_setup_pathname())

    def get_setup_int(self, name=None, system=None, architecture=None, version=None):
        if not version:
            version = DEFAULT
        rets = os.path.join(self.get_install_root_dir(), name, '$OSG_SYSTEM', '$OSG_ARCH', version)
        return rets

    def _is_ok_dirname(self, name):
        if name:
            if name in self.EXCLUDED_DIR:
                return False
            for i in self.EXCLUDED_PREFIX:
                if name.startswith(i):
                    return False
            for i in self.EXCLUDED_SUFFIX:
                if name.endswith(i):
                    return False
            return True
        return False

    def list(self, name=None, system=None, architecture=None, version=None, return_default=False, short=True):
        res = {}
        res_def = {}
        if name:
            name_list = [name]
        else:
            name_list = filter(self._is_ok_dirname, os.listdir(self.get_install_root_dir()))
        for i in name_list:
            res[i] = {}
            if system:
                sys_list = [system]
            else:
                sys_list = filter(self._is_ok_dirname, os.listdir(os.path.join(self.get_install_root_dir(), i)))
                if short:
                    sys_list = [nl for nl in sys_list
                                if not os.path.islink(os.path.join(self.get_install_root_dir(), i, nl))]
            for j in sys_list:
                res[i][j] = {}
                if architecture:
                    arch_list = [architecture]
                else:
                    arch_list = filter(self._is_ok_dirname, os.listdir(os.path.join(self.get_install_root_dir(), i, j)))
                    if short:
                        arch_list = [nl for nl in arch_list
                                     if not os.path.islink(os.path.join(self.get_install_root_dir(), i, j, nl))]
                for k in arch_list:
                    version_list = os.listdir(os.path.join(self.get_install_root_dir(), i, j, k))
                    if version:
                        res[i][j][k] = [version]
                    else:
                        if short:
                            tmp_dir = os.path.join(self.get_install_root_dir(), i, j, k)
                            # leave aliases? remove only defaults?
                            res[i][j][k] = [ nl for nl in version_list
                                             if not os.path.dirname(os.readlink(os.path.join(tmp_dir, nl))) == '']
                        else:
                            res[i][j][k] = version_list
                    if return_default and DEFAULT in version_list:
                        res_def["%s-%s-%s" % (i, j, k)] = \
                            os.readlink(os.path.join(self.get_install_root_dir(), i, j, k, DEFAULT))
        if return_default:
            return res, res_def
        return res



    def print_list(list_dic, list_default=None):
        rets = []
        mytable = [('SOFTWARE', 'SYSTEM', 'ARCH', 'VERSION')]
        for i in list_dic.keys():
            for j in list_dic[i].keys():
                for k, k_val in list_dic[i][j].items():
                    for l in k_val:
                        if list_default:
                            if l==list_default["%s-%s-%s" % (i, j, k)]:
                                mytable.append((i, j, k, "%s (default)" % l))
                                continue
                        mytable.append((i, j, k, l))
        col_width = [max(len(x) for x in col) for col in zip(*mytable)]
        for line in mytable:
            # print " ".join("{:{}}".format(x, col_width[i]) for i, x in enumerate(line))
            print "  ".join(x.ljust(col_width[i]) for i, x in enumerate(line))
        #print "| " + " | ".join("{:{}}".format(x, col_width[i])
        #                        for i, x in enumerate(line)) + " |"

        print '\n'.join(rets)
    print_list = staticmethod(print_list)

    def print_list_old(list_dic, list_default=None):
        rets = []
        for i in list_dic.keys():
            for j in list_dic[i].keys():
                for k, k_val in list_dic[i][j].items():
                    for l in k_val:
                        #if list_default and l==DEFAULT:
                        #    rets.append("%s \t%s \t%s \t%s (%s)" %
                        #                (i, j, k, l, list_default["%s-%s-%s" % (i, j, k)]))
                        if list_default:
                            if l==list_default["%s-%s-%s" % (i, j, k)]:
                                rets.append("%s \t%s \t%s \t%s (default)" %
                                            (i, j, k, l))
                                continue
                        rets.append("%s \t%s \t%s \t%s" % (i, j, k, l))
        print '\n'.join(rets)




    def remove(self, package):
        # Removes the installed package and the link tree
        pass

    def update(self, package, archive=True):
        # archive (if not false) and install
        # what if package not there? should install?
        if self.is_installed(package):
            # what if package not there? should install?
            pass
        if archive:
            self.archive(package)
        # Force install to install on top of existing
        self.install(package, force=True, no_link=True)
        pass

    def archive(self, package):
        pass




"""
palms -i (--install) name arch ver URL
    -f force install
    -d default version
    -n accept new keyword
    --syncdb
    -s --setup
    -r (--remove)

New idea, more similar to yum, apt-get
palms [options] command [packages]

Commands
setup
install
remove
erase/remove
update/upgrade
check
?reinstall
version

"""


def oldmain():
    from optparse import OptionParser
    #cmd_list = ['debug', 'getval', 'setval', 'getlines', 'getfile', 'get_config_files']
    usage = 'Usage: %prog [options] URL pkg_name [pkg_platform [pkg_version]]'
    parser = OptionParser(usage=usage)
    #parser.add_option("-l", "--literal", dest="literal",
    #    help='literal interpretation', action="store_true", default=False)
    # commands (set the group
    parser.add_option("-i", "--install", dest="command",
        help='Install the package', action="store", default=None)
    parser.add_option("-r", "--remove", dest="command",
        help='Remove the package', action="store", default=None)
    parser.add_option("-u", "--update", dest="command",
        help='Update the package', action="store", default=None)
    parser.add_option("-l", "--list", dest="command",
        help='List the installed packages', action="store", default=None)
    parser.add_option("-v", "--verbose", "--debug", dest="verbose",
        help="Print verbose output", action="store_true", default=False)
    parser.add_option("-v", "--verbose", "--debug", dest="verbose",
        help="Print verbose output", action="store_true", default=False)
    parser.add_option("-v", "--verbose", "--debug", dest="verbose",
        help="Print verbose output", action="store_true", default=False)
    parser.add_option("--infiles", dest="infiles",
        help='Additional input files for the job (comma separated list)', action="store", default=None)
    parser.add_option("-o", "--output", dest="output",
        help='Standard output for the job', action="store", default=None)
    parser.add_option("-e", "--error", dest="error",
        help='Standard error for the job', action="store", default=None)
    parser.add_option("--outfiles", dest="outfiles",
        help='Additional output files for the job (comma separated list)', action="store", default=None)


ustring = "Usage: palms [options] command [arguments]"
commands = ['setup', 'archive', 'install', 'remove', 'update', 'check', 'version', 'list', 'list-long']
options = """    -f     force install
    -d      default version
    -r DIR  root directory
    -h      help
    -u URL  tar file name
"""
arguments = """ palms list
 palms -u URL install name [system [architecture [version]]]
 palms setup/archive/remove/update name [system [architecture [version]]]
"""

"""
palms -i (--install) name arch ver URL
    -f force install
    -d default version
    -n accept new keyword
    --syncdb
    -s --setup
    -r (--remove)

New idea, more similar to yum, apt-get
palms [options] command [packages]

Commands
setup
install
remove
erase/remove
update/upgrade
check
?reinstall
version
"""

def usage():
    rets = ustring
    rets += "\nOptions:\n%s" % options
    rets += "\nCommands:\n %s" % ','.join(commands)
    rets += "\nArguments:\n%s" % arguments
    print rets

def is_write_command(command):
    if command:
        if command == 'setup' or command.startswith('list'):
            return False
    return True


if __name__ == "__main__" :
    import getopt
    try:
        # Using gnu_getopt instead of getopt to parse options after the arguments
        #  e.g. palms setup -r /tmp myapp
        opts, args = getopt.gnu_getopt(sys.argv[1:], "fdhvr:u:", ["force", "default", "help", "url=", "root-dir=", "shell="])
        #except getopt.GetoptError as err:
    except getopt.GetoptError:
        # print help information and exit:
        #print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    force = False
    default = False
    verbose = False
    command = None
    root_dir = None #'.'
    package_url = None
    user_shell = None
    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-d", "--default"):
            default = True
        elif o in ("-f", "--force"):
            force = True
        elif o in ("-r", "--root-dir"):
            root_dir = a
        elif o in ("-u", "--url"):
            package_url = a
        elif o in ("--shell"):
            user_shell = a
        else:
            assert False, "unhandled option"

    if not args:
        # must specify a command
        usage()
        sys.exit(2)
    command = args[0]
    if not command in commands:
        # not valid command
        usage()
        sys.exit(2)


    tmp_dir = root_dir
    if not tmp_dir:
        if is_write_command(command):
            tmp_dir = '.'
        else:
            tmp_dir = Palms.DEFAULT_ROOT_DIR

    try:
        p = Palms(tmp_dir, is_write_command(command))
    except OSError:
        print 'ERROR:_Palms root dir does not exist: %s' % tmp_dir
        sys.exit(1)

    if user_shell:
        p.set_shell(user_shell)


    # commands = ['setup', 'install', 'remove', 'update', 'check', 'version', 'list']
    if command == 'list' or command == 'list-long':
        if command == 'list':
            short = True
        else:
            short = False
        if default:
            a, b = p.list(return_default=True, short=short)
            p.print_list(a, b)
        else:
            p.print_list(p.list(short=short))
        sys.exit()
        # TODO: add commands with no arguments
        # elif command ==
    else:
        if not len(args)>1:
            print "Invalid syntax: %s requires arguments" % command
            usage()
            sys.exit(2)
        pa = Package(*args[1:])
        if command == 'install':
            if not package_url:
                print "Package URL is missing"
                usage()
                sys.exit(2)
            pa.set_tarball_file(package_url)
            retv = p.install(pa)
            if verbose:
                if retv:
                    print "Package %s installed in %s" % (pa.name, retv)
                else:
                    print "Failed to install"
            if retv:
                sys.exit()
            sys.exit(2)
        elif command == 'remove':
            retv = p.remove(pa)
        elif command == 'update':
            retv = p.update(pa, True)
        elif command == 'archive':
            retv = p.archive(pa)
        elif command == 'setup':
            if pa.name == 'FAKE':
                print 'source "%s/test.%s"' % (p.root_dir, p.get_shell())
                sys.exit(0)
            retv = p.get_setup(pa)
            if p.is_installed(pa):
                print 'source "%s/setup.%s"' % (retv, p.get_shell())
            else:
                if verbose:
                    print "%s is not installed. File not found: %s" % (pa.name, retv)
                sys.exit(1)
        else:
            print "Unimplemented command"
            sys.exit(1)



