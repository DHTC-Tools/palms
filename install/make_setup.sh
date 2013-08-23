#!/bin/sh

# Default install directory
INSTALL_DIR=/cvmfs/oasis.opensciencegrid.org/org/palms

if [ ! -z $1 ]; then
  if [ "$1" == "OASIS" ]; then
    INSTALL_DIR=/cvmfs/oasis.opensciencegrid.org/org/palms
  else
    INSTALL_DIR="$1"
  fi
fi

if [ ! -z $2 ]; then
  PALMS_DIR="$2"
else
  PALMS_DIR="$1/palms"
fi

if [ ! -d $PALMS_DIR ]; then
  mkdir -p $PALMS_DIR/bin
fi

# setup.sh
cat > "$PALMS_DIR/setup.sh" << EOF
PATH="$PATH:$PALMS_DIR/bin"
export PATH
# palmsdosetup () {  eval \`$PALMS_DIR/bin/palms setup "\$@"\`; }
load () { eval "\$("\$@")"; }
palmsdosetup () { x="\$(palms setup "\$@")" && eval "\$x" || echo "PALMS setup failed: \$x"; }
EOF

# setup.csh
cat > "$PALMS_DIR/setup.csh" << EOF
setenv PATH="$PATH:$PALMS_DIR/bin"
#alias palmsdosetup 'eval \`'$PALMS_DIR/bin/palms' setup \\!*\`'
alias palmsdosetup 'x=\`'$PALMS_DIR/bin/palms' setup \\!*\` && eval "\$x" || echo "PALMS setup failed: \$x"' 
EOF

# setup (shell independent)
cat > "$PALMS_DIR/setup" << EOF
# Shell-independent setup
source $PALMS_DIR/setup.\`$PALMS_DIR/bin/shellselector -q\`
EOF

# Copying shellselector and linking the setup files
cp `dirname $0`/shellselector $PALMS_DIR/bin/
ln -s $PALMS_DIR/setup $INSTALL_DIR/setup
ln -s $PALMS_DIR/setup.sh $INSTALL_DIR/setup.sh
ln -s $PALMS_DIR/setup.csh $INSTALL_DIR/setup.csh

# Copying palms if not there
if [ ! -f $PALMS_DIR/bin/palms ]; then
  cp `dirname $0`/../bin/palms $PALMS_DIR/bin/
fi
