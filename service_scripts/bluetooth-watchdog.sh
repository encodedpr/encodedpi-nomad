#!/bin/bash

LOG="/var/log/bluetooth-watchdog.log"
EXPECTED=("hci0" "hci1")

touch "$LOG"

exec 200>/var/run/bluetooth-watchdog.lock
flock -n 200 || exit 0

log(){
    echo "$(date '+%F %T') - $1" >> "$LOG"
}

reset_adapter(){
    ADAPTER=$1
    log "Resetting adapter: $ADAPTER"
    hciconfig "$ADAPTER" reset >/dev/null 2>&1
    sleep 2
}

reset_usb_adapter(){
    ADAPTER=$1
    DEVPATH=$(readlink -f /sys/class/bluetooth/$ADAPTER/device)

    if [[ "$DEVPATH" != *"/usb"* ]]; then
        log "Skipping USB reset for internal adapter: $ADAPTER"
        return
    fi

    if ! command -v usbreset >/dev/null 2>&1; then
        log "usbreset not installed for $ADAPTER"
        return
    fi

    USBDEV=$(udevadm info -q name -p "$DEVPATH" 2>/dev/null)

    if [ -n "$USBDEV" ]; then
        log "Resetting USB device: $ADAPTER ($USBDEV)"
        usbreset "/dev/$USBDEV" >/dev/null 2>&1
        sleep 2
    fi
}

restart_bt(){
    log "Restarting bluetooth service"
    systemctl restart bluetooth
    sleep 4
}

reboot_system(){
    log "Final recovery: rebooting system"
    /sbin/reboot
}

hci_test(){
    ADAPTER=$1
    timeout 2 hcitool -i "$ADAPTER" cmd 0x04 0x0001 >/dev/null 2>&1
}

check_adapters(){
    local FAILURE=0

    for ADAPTER in "${EXPECTED[@]}"; do

        if [ ! -d "/sys/class/bluetooth/$ADAPTER" ]; then
            log "Adapter missing: $ADAPTER"
            restart_bt
            FAILURE=1
            continue
        fi

        if ! hciconfig "$ADAPTER" | grep -q "RUNNING"; then
            log "Adapter not running: $ADAPTER"
            reset_adapter "$ADAPTER"
            reset_usb_adapter "$ADAPTER"
            restart_bt
            FAILURE=1
            continue
        fi

        if ! hci_test "$ADAPTER"; then
            log "HCI not responding: $ADAPTER"
            reset_adapter "$ADAPTER"
            reset_usb_adapter "$ADAPTER"
            restart_bt
            FAILURE=1
        else
            log "$ADAPTER OK"
        fi

    done

    return $FAILURE
}

log "Bluetooth watchdog check started"

# First attempt
check_adapters
RESULT=$?

if [ $RESULT -ne 0 ]; then
    log "Failure detected, retrying in 2 minutes"
    sleep 120

    # Second attempt
    check_adapters
    RESULT=$?

    if [ $RESULT -ne 0 ]; then
        reboot_system
    else
        log "Recovered after retry"
    fi
fi

log "Bluetooth watchdog check completed"
