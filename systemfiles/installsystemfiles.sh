#!/bin/bash
sudo cp ourapost.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/ourapost.sh

sudo cp ourapost.service /etc/systemd/system/
sudo cp ourapost.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now ourapost.timer