#!/bin/bash

# Stop TibiaHub Services

echo "⛔ Stopping TibiaHub services..."
echo ""

pm2 stop tibiahub-api tibiahub-frontend

echo ""
echo "✅ Services stopped!"
echo ""
echo "📊 Current status:"
pm2 list | grep tibiahub

echo ""
echo "💡 To restart, run: ./start.sh"
