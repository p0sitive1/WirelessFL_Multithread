#!/bin/bash

## prepare Raspberry Pi

USERNAME="ubuntu"

HOSTS="10.20.30.87 10.20.30.84 10.20.30.29"

SCRIPT="pwd; ls"

# Transfer new version
# cd ..
DIR="$( cd "$( dirname "$0" )" && pwd )"
echo ${DIR}

# copy ssh-key
for HOSTNAME in ${HOSTS} ; do
    echo ${HOSTNAME}
    # copy ssh key 
    ssh-copy-id -i ubuntu@${HOSTNAME}

    # remove old version code 
    ssh -o StrictHostKeyChecking=no -l ${USERNAME} ${HOSTNAME} "rm -rf /home/ubuntu/fed-iot/WirelessFL"

    # Upload new code 
    rsync -r -avu -e ssh --stats --exclude=.git --exclude=data/synthetic --exclude=log/* --exclude=cache/* "${DIR}" ubuntu@${HOSTNAME}:/home/ubuntu/fed-iot
    scp -rp "${DIR}" ubuntu@${HOSTNAME}:/home/ubuntu/fed-iot/

    # Install necessary library
    ssh -o StrictHostKeyChecking=no -l ${USERNAME} ${HOSTNAME} "sudo su - <<'EOF' 
    python -m pip install pickle5
    python -m pip install tensorboardX"
    echo ${HOSTNAME}
done
