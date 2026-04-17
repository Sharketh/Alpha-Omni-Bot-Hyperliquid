#!/bin/bash

# Nama service harus sama dengan nama file .service yang kamu buat di /etc/systemd/system/
SERVICE_NAME="bot.service"
LOG_FILE="/var/log/bot_restart.log"

echo "------------------------------------------" >> $LOG_FILE
echo "Initiating Restart: $(date)" >> $LOG_FILE

# Melakukan restart service
if sudo systemctl restart $SERVICE_NAME; then
    echo "✅ Success: $SERVICE_NAME restarted successfully."
    echo "Status: SUCCESS at $(date)" >> $LOG_FILE
else
    echo "❌ Error: Failed to restart $SERVICE_NAME."
    echo "Status: FAILED at $(date)" >> $LOG_FILE
fi

echo "------------------------------------------" >> $LOG_FILE
