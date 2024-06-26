#!/usr/bin/bash
PASSWD=$1
echo "${PASSWD}" | sudo -S echo ""
if [ -f "/etc/systemd/system/CBTransf_ipsound_public.service" ]
then
    sudo systemctl stop CBTransf_ipsound_public.service && sudo rm /etc/systemd/system/CBTransf_ipsound_public.service -fr
fi
sudo cp CBTransf_ipsound_public.service /etc/systemd/system/ -fr && sudo systemctl daemon-reload && sudo systemctl enable CBTransf_ipsound_public.service && sudo systemctl start CBTransf_ipsound_public.service
if [ -f "/etc/logrotate.d/CBTransf_ipsound.log" ]
then
    sudo rm /etc/logrotate.d/CBTransf_ipsound.log -fr
fi
sudo cp CBTransf_ipsound.log /etc/logrotate.d/ -fr && sudo systemctl restart logrotate.service