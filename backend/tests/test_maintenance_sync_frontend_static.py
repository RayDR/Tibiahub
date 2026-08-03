from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_frontend_routes_real_auth_gate_and_assistance_are_wired():
    app = read("frontend/src/App.tsx")
    gate = read("frontend/src/components/maintenance/MaintenanceGate.tsx")
    screen = read("frontend/src/components/maintenance/MaintenanceScreen.tsx")
    assert '<Route path="assistance/raffles" element={<RaffleAssistance />} />' in app
    assert '<Route path="maintenance" element={<MaintenanceControl />} />' in app
    assert '<Route path="maintenance/data" element={<DataMaintenance />} />' in app
    assert "<MaintenanceGate>" in app
    assert "user?.is_superuser" in gate
    assert "navigate('/login?maintenance=1')" in gate
    assert 'to="/login?maintenance=1"' in screen
    assert "localStorage.setItem('token'" not in gate + screen


def test_full_sync_dashboard_uses_durable_api_shared_confirmation_and_safe_defaults():
    dashboard = read("frontend/src/pages/Admin/FullSyncDashboard.tsx")
    service = read("frontend/src/services/fullSync.ts")
    data_tools = read("frontend/src/pages/Admin/DataTools.tsx")
    assert "maintenance_enabled: true" in dashboard
    assert "continue_on_error: true" in dashboard
    assert "include_knowledge: true" in dashboard
    assert "include_guild_rosters: true" in dashboard
    assert "useConfirmation" in dashboard
    assert "window.confirm" not in dashboard
    assert "'/admin/sync/full'" in service
    assert "<FullSyncDashboard />" in data_tools


def test_worker_is_dedicated_and_request_process_threads_are_removed():
    ecosystem = read("ecosystem.config.js")
    worker = read("backend/app/workers/sync_worker.py")
    sync_service = read("backend/app/services/sync_service.py")
    assert "name: 'tibiahub-sync-worker'" in ecosystem
    assert "args: '-m app.workers.sync_worker'" in ecosystem
    assert "claim_next" in worker and "_run_job_sync" in worker
    assert "ThreadPoolExecutor" not in sync_service
