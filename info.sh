#!/bin/bash

# Quick Info Script - TibiaHub (formerly Tibia Bestiary)

echo "============================================="
echo "🐲 TibiaHub - System Information"
echo "============================================="
echo ""
echo "📍 Location: /forge/tibiahub"
echo ""
echo "🌐 Access URLs:"
echo "  Frontend:  https://tibiahub.domoforge.com"
echo "  API:       https://tibiahub.domoforge.com/api/v1/"
echo "  API Docs:  https://tibiahub.domoforge.com/docs"
echo "  ReDoc:     https://tibiahub.domoforge.com/redoc"
echo ""
echo "📊 PM2 Services:"
pm2 list | grep tibiahub
echo ""
echo "💾 Database:"
if /forge/tibiahub/scripts/verify-postgres.sh >/dev/null 2>&1; then
    echo "  ✅ PostgreSQL is reachable and at Alembic head"
else
    echo "  ❌ PostgreSQL verification failed"
fi
echo ""
echo "📝 Quick Commands:"
echo "  Start:     cd /forge/tibiahub && ./start.sh"
echo "  Stop:      cd /forge/tibiahub && ./stop.sh"
echo "  Status:    pm2 status | grep tibiahub"
echo "  Logs API:  pm2 logs tibiahub-api"
echo "  Logs Job:  pm2 logs tibiahub-raffle-scheduler"
echo "  Logs UI:   pm2 logs tibiahub-frontend"
echo "  Monitor:   pm2 monit"
echo ""
echo "📚 Documentation:"
echo "  README.md              - General documentation"
echo "  MIGRATION_COMPLETED.md - Migration details from tibia-bestiary"
echo ""
echo "============================================="
