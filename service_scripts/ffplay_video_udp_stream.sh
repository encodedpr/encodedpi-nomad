#!/bin/bash

sudo -u encoded pkill ffplay
#sudo -u encoded pkill firefox
export DISPLAY=:0
#export GDK_BACKEND=x11

#RES=$(xdpyinfo | grep dimensions | awk '{print $2}')
#W=$(echo $RES | cut -dx -f1)
#H=$(echo $RES | cut -dx -f2)
#sudo -u encoded nohup env DISPLAY=:0 ffplay -volume 0 -x $W -y $H -i udp://239.255.0.1:1234 >/home/encoded/ffplay.log 2>&1 &

#sudo -u encoded firefox encodedpi:8123/ &
#sleep 5
sudo -u encoded ffplay -window_title ffplay_window -x 1920 -y 1040 -volume 0 -i udp://239.255.0.1:1234 >/dev/null 2>&1 &

#FFPLAY_WIN_ID=$(wmctrl -l | grep -i ffplay | awk '{print $1}' | head -n1)
#if [ -n "$FFPLAY_WIN_ID" ]; then
#    wmctrl -i -r "$FFPLAY_WIN_ID" -b add,maximized_vert,maximized_horz
#sudo -u encoded wmctrl -r "udp://239.255.0.1:1234" -e 0,0,0,1440,1080
#fi
#pkill -SIGUSR1 labwc
