#!/bin/bash

# Start TibiaHub Services

echo "🚀 Starting TibiaHub services..."
echo ""

# Check if ecosystem.config.js exists
if [ ! -f "ecosystem.config.js" ]; then
    echo "❌ Error: ecosystem.config.js not found in $(pwd)"
    exit 1
fi

# Start with PM2
pm2 start ecosystem.config.js

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Current status:"
pm2 list | grep tibiahub

echo ""
echo "🌐 Access the application at:"
echo "  https://tibiahub.domoforge.com"
echo ""
echo "📝 View logs:"
echo "  Backend:  pm2 logs tibiahub-api"
echo "  Frontend: pm2 logs tibiahub-frontend"
