#!/bin/bash

# As we are dynamically creating the Jenkins node using the OpenStack plugin,
# we require additional configurations to enable us to use the system for
# executing the cephci test suites. This script performs the required changes.

# Options
#   0 -> Installs python along with cephci required packages
#   1 -> Configures the agent with necessary CI packages
#   2 -> 0 + 1 along with deploying postfix package
#   3 -> 0 + 1 along with rclone package
#   4 -> 0 + 1 along with teuthology clone and install

echo "Initialize Node"
# Workaround: Disable IPv6 to have quicker downloads
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1

sudo yum install -y git-core zip unzip
sudo dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
sudo yum install -y p7zip
sudo curl -LO https://github.com/mikefarah/yq/releases/download/v4.9.6/yq_linux_amd64
sudo chmod +x yq_linux_amd64;
sudo mv yq_linux_amd64 /usr/local/bin/yq
yq --version

# Mount reesi for storing logs
if [ ! -d "/cephh/cephci-jenkins" ]; then
    sudo mkdir -p /ceph
    wget http://magna002.ceph.redhat.com/cephci-jenkins/.cephci_1.yaml -O ${HOME}/.cephci_1.yaml
    mount_creds_mon_ips=$(yq eval '.mount_creds.mon_ips' ${HOME}/.cephci_1.yaml)
    mount_creds_mount_point=$(yq eval '.mount_creds.mount_point' ${HOME}/.cephci_1.yaml)
    mount_creds_client_name=$(yq eval '.mount_creds.client_name' ${HOME}/.cephci_1.yaml)
    mount_creds_secret=$(yq eval '.mount_creds.secret' ${HOME}/.cephci_1.yaml)
    mount_command="sudo mount -t ceph $mount_creds_mon_ips $mount_creds_mount_point -o name=$mount_creds_client_name,secret=$mount_creds_secret"

    # Display the resulting mount command
    echo "Mount Command:"
    echo "$mount_command"

    # Execute the mount command
    eval "$mount_command"
    echo "Mounting ressi004"
#    sudo mkdir -p /ceph
#    sudo mount -t nfs -o sec=sys,nfsvers=4.1 reesi004.ceph.redhat.com:/ /ceph
fi

if [ ${1:-0} -ne 1 ]; then
    sudo yum install -y wget python3
    # Copy the config from internal file server to the Jenkins user home directory
    wget http://magna002.ceph.redhat.com/cephci-jenkins/.cephci.yaml -O ${HOME}/.cephci.yaml
    sudo mkdir -p /root/.aws
    sudo wget http://magna002.ceph.redhat.com/cephci-jenkins/.ibm-cos-aws.conf -O /root/.aws/credentials


    # Install cephci prerequisites
    rm -rf .venv
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

# Monitoring jobs have a need to send email using smtplib that requires postfix
if [ ${1:-0} -eq 2 ]; then
    postfix_rpm=$(rpm -qa | grep postfix | wc -l)
    if [ ${postfix_rpm} -eq 0 ]; then
        sudo yum install -y postfix
    fi
    systemctl is-active --quiet postfix || sudo systemctl restart postfix
fi

# Post results workflow requires to sync from COS
if [ ${1:-0} -eq 3 ]; then
    # Install rclone
    curl https://rclone.org/install.sh | sudo bash || echo 0
    mkdir -p ${HOME}/.config/rclone
    wget http://magna002.ceph.redhat.com/cephci-jenkins/.ibm-cos.conf -O ${HOME}/.config/rclone/rclone.conf

fi

echo "Done bootstrapping the Jenkins node."
