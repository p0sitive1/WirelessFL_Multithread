
#!/bin/bash

# run pi
USERNAME="ubuntu"

HOSTS="10.20.30.87 10.20.30.84"


# execute program
for HOSTNAME in ${HOSTS} ; do

    ssh -o StrictHostKeyChecking=no -l ${USERNAME} ${HOSTNAME} "sudo su - <<'EOF' 
    cd /home/ubuntu/fed-iot/WirelessFL
    python app.py --mode client > log.txt &"
    echo ${HOSTNAME}
    sleep 2
done