#!/bin/sh

# Default install directory
INSTALL_DIR=/cvmfs/oasis.opensciencegrid.org/osg/palms

function help_msg {
  cat << EOF
$0 [ options ]
 Edit $0 to set the default options (install dir)
 -h       print this help message
 -d DIR   set an install directory (for the setup scripts)
       This is the path that will be seen by the users
       OASIS is a keyword for "/cvmfs/oasis.opensciencegrid.org/org/palms"
 -p DIR   set the directory where palms binaries installed (as ssen by the users)
          [./palms/ from the install dir]
 -a DIR   set setup links directory [=install directory]
       You need to set this if to copy the files you must use a different path 
       E.g. On the OASIS server you must write on a path that is different from the
       final one.
 -b DIR   set file directory [=palms directory]
       You need to set this if to copy the files you must use a different path 
       E.g. On the OASIS server you must write on a path that is different from the
       final one.
Example: $0 -d OASIS -a /net/nas01/Public/ouser.osg/palms
EOF
}



while getopts hd:p:a:b: option
do
  case "${option}"
  in
  "h") help_msg; exit 0;;
  "d") INSTALL_DIR="${OPTARG}";;
  "p") OPT_PALMS_DIR="${OPTARG}";;
  "a") OPT_LINK_DIR="${OPTARG}";;
  "b") OPT_COPY_DIR="${OPTARG}";;
  esac
done


if [ "$INSTALL_DIR" == "OASIS" ]; then
  INSTALL_DIR=/cvmfs/oasis.opensciencegrid.org/osg/palms
fi

if [ -z $OPT_PALMS_DIR ]; then
  PALMS_DIR="$INSTALL_DIR/palms"
  RELATIVE_LINK="palms"
else
  PALMS_DIR="$OPT_PALMS_DIR"
fi

if [ ! -d $PALMS_DIR ]; then
  mkdir -p $PALMS_DIR/bin
fi

# Final directory
if [ -z $OPT_LINK_DIR ]; then
  LINK_DIR="$PALMS_DIR"
else
  LINK_DIR="$OPT_LINK_DIR"
fi

if [ -z $OPT_COPY_DIR ]; then
  if [ -z $OPT_LINK_DIR ]; then
    COPY_DIR="$PALMS_DIR"
  else
    if [ "x$OPT_PALMS_DIR" != "x" ];then
      echo "WARNING: you used options -p and -a but not -b. Make sure the paths are not inconsistent."
    fi
    COPY_DIR="$LINK_DIR/palms"
  fi
else
  COPY_DIR="$OPT_COPY_DIR"
fi



# To make the setup scripts 
# setup.sh
if [ -z $RELATIVE_LINK ]; then
  cat > "$COPY_DIR/setup.sh" << EOF
# Shell setup for PALMS
PATH="$PATH:$PALMS_DIR/bin"
export PATH
# palmsdosetup () {  eval \`$PALMS_DIR/bin/palms setup "\$@"\`; }
load () { eval "\$("\$@")"; }
palmsdosetup () { x="\$(palms setup "\$@")" && eval "\$x" || echo "PALMS setup failed: \$x"; }
EOF
else
  cat > "$COPY_DIR/setup.sh" << EOF
# Shell setup for PALMS - relocatable version
# This file is sourced, so \$BASH_SOURCE is used instead of \$0
SCRIPTPATH=\$( cd "\$(dirname "\$BASH_SOURCE")" ; pwd -P )
if [ -d \$SCRIPTPATH/bin ]; then 
  PATH="$PATH:\$SCRIPTPATH/bin"
else
  PATH="$PATH:\$SCRIPTPATH/$RELATIVE_LINK/bin"
fi
export PATH
# palmsdosetup () {  eval \`$PALMS_DIR/bin/palms setup "\$@"\`; }
load () { eval "\$("\$@")"; }
palmsdosetup () { x="\$(palms setup "\$@")" && eval "\$x" || echo "PALMS setup failed: \$x"; }
EOF
fi

# setup.csh
# CShell setup for PALMS
cat > "$COPY_DIR/setup.csh" << EOF
setenv PATH "$PATH:$PALMS_DIR/bin"
#alias palmsdosetup 'eval \`'$PALMS_DIR/bin/palms' setup \\!*\`'
alias palmsdosetup 'x=\`'$PALMS_DIR/bin/palms' setup \\!*\` && eval "\$x" || echo "PALMS setup failed: \$x"' 
EOF

# setup (shell independent)
cat > "$COPY_DIR/setup" << EOF
# Shell-independent setup
source $PALMS_DIR/setup.\`$PALMS_DIR/bin/shellselector -q\`
EOF

# Copying shellselector and linking the setup files
cp `dirname $0`/shellselector $PALMS_DIR/bin/
if [ -z $RELATIVE_LINK ]; then
  ln -s $PALMS_DIR/setup $LINK_DIR/setup
  ln -s $PALMS_DIR/setup.sh $LINK_DIR/setup.sh
  ln -s $PALMS_DIR/setup.csh $LINK_DIR/setup.csh
else
  ln -s $RELATIVE_LINK/setup $LINK_DIR/setup
  ln -s $RELATIVE_LINK/setup.sh $LINK_DIR/setup.sh
  ln -s $RELATIVE_LINK/setup.csh $LINK_DIR/setup.csh
fi

# Copying palms if not there
if [ ! -f $COPY_DIR/bin/palms ]; then
  cp `dirname $0`/../bin/palms $COPY_DIR/bin/
fi
