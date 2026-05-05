#!/usr/bin/env python3
"""Integration checks for original stabilization scope (P1-P9)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone

import requests


BASE_URL = "http://127.0.0.1:8001/api/v1"


def _print(label: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}: {detail}")


def _login(username: str, password: str) -> str:
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"login failed user={username} code={response.status_code} body={response.text[:300]}")
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_announcement(token: str, suffix: str) -> int:
    payload = {"title": f"A-{suffix}", "content": "test", "type": "general"}
    response = requests.post(f"{BASE_URL}/guild/announcements", headers=_auth_headers(token), json=payload, timeout=15)
    response.raise_for_status()
    return int(response.json()["id"])


def _create_guild_event(token: str, suffix: str) -> int:
    now = datetime.now(timezone.utc)
    payload = {
        "title": f"E-{suffix}",
        "description": "test",
        "start_time": (now + timedelta(minutes=30)).isoformat(),
        "end_time": (now + timedelta(hours=1)).isoformat(),
        "type": "other",
    }
    response = requests.post(f"{BASE_URL}/guild/events", headers=_auth_headers(token), json=payload, timeout=15)
    response.raise_for_status()
    return int(response.json()["id"])


def _create_raffle(token: str, suffix: str) -> int:
    payload = {
        "title": f"R-{suffix}",
        "description": "test",
        "guild_name": "TestGuild",
        "prizes": [{"name": "Gold Prize", "reward": "100k", "order_index": 1}],
    }
    response = requests.post(f"{BASE_URL}/raffles/", headers=_auth_headers(token), json=payload, timeout=20)
    response.raise_for_status()
    return int(response.json()["id"])


def _is_in_list(url: str, token: str, entity_id: int) -> tuple[bool, int]:
    response = requests.get(url, headers=_auth_headers(token), timeout=15)
    if response.status_code != 200:
        return False, response.status_code
    ids = {int(item.get("id")) for item in response.json() if item.get("id") is not None}
    return entity_id in ids, response.status_code


def main() -> int:
    if os.environ.get("TIBIAHUB_ALLOW_TEST_DATA") != "1":
        raise RuntimeError("Refusing to run validation that creates test data without TIBIAHUB_ALLOW_TEST_DATA=1")

    print(f"BASE_URL={BASE_URL}")

    # Auth bootstrap expectation: users created by scripts/bootstrap_test_users.py
    admin_token = _login("admin", "admin123")
    leader_token = _login("leader_test", "leader123")
    user_token = _login("user_test", "user123")
    _print("auth_tokens", True, "admin/leader/user tokens issued")

    # 1) /guild/features without token -> 401
    r = requests.get(f"{BASE_URL}/guild/features", timeout=10)
    _print("guild_features_without_token", r.status_code == 401, f"status={r.status_code}")

    # 2) /guild/features with token -> 200
    r = requests.get(f"{BASE_URL}/guild/features", headers=_auth_headers(admin_token), timeout=10)
    _print("guild_features_with_token", r.status_code == 200, f"status={r.status_code} body={r.text[:180]}")

    # 3) start sync returns quickly with job_id
    t0 = time.monotonic()
    r = requests.post(f"{BASE_URL}/admin/sync/bestiary/start?source=creatures&mode=auto", headers=_auth_headers(admin_token), timeout=20)
    dt_ms = int((time.monotonic() - t0) * 1000)
    start_ok = r.status_code == 200 and bool(r.json().get("job_id"))
    job_id = r.json().get("job_id") if r.status_code == 200 else None
    _print("sync_start_quick_jobid", start_ok, f"status={r.status_code} latency_ms={dt_ms} body={r.text[:220]}")

    # 4) no freeze during sync (bestiary + guild endpoints responsive)
    t1 = time.monotonic()
    c = requests.get(f"{BASE_URL}/creatures/?limit=5", timeout=15)
    c_ms = int((time.monotonic() - t1) * 1000)
    t2 = time.monotonic()
    g = requests.get(f"{BASE_URL}/guild/features", headers=_auth_headers(admin_token), timeout=15)
    g_ms = int((time.monotonic() - t2) * 1000)
    _print("sync_non_blocking_creatures", c.status_code == 200, f"status={c.status_code} latency_ms={c_ms}")
    _print("sync_non_blocking_guild_features", g.status_code == 200, f"status={g.status_code} latency_ms={g_ms}")

    # 5) cancel sync transitions to cancelled
    cancel_ok = False
    if job_id:
        rc = requests.post(f"{BASE_URL}/admin/sync/jobs/{job_id}/cancel", headers=_auth_headers(admin_token), timeout=15)
        last_body = rc.text[:220]
        status_value = "unknown"
        for _ in range(90):
            time.sleep(1)
            rs = requests.get(f"{BASE_URL}/admin/sync/jobs/{job_id}", headers=_auth_headers(admin_token), timeout=10)
            if rs.status_code != 200:
                continue
            status_value = rs.json().get("status", "unknown")
            last_body = rs.text[:220]
            if status_value == "cancelled":
                cancel_ok = True
                break
            if status_value in {"completed", "failed"}:
                break
        _print("sync_cancelled", cancel_ok, f"cancel_status={status_value} cancel_call={rc.status_code} job={job_id} body={last_body}")
    else:
        _print("sync_cancelled", False, "job_id missing; cannot cancel")

    # 6) Soft-delete as admin/leader and 403 for normal user
    suffix = str(int(time.time()))
    ann_admin = _create_announcement(admin_token, f"admin-{suffix}")
    evt_admin = _create_guild_event(admin_token, f"admin-{suffix}")
    raf_admin = _create_raffle(admin_token, f"admin-{suffix}")

    da = requests.delete(f"{BASE_URL}/guild/announcements/{ann_admin}", headers=_auth_headers(admin_token), json={"reason": "test"}, timeout=15)
    de = requests.delete(f"{BASE_URL}/guild/events/{evt_admin}", headers=_auth_headers(admin_token), json={"reason": "test"}, timeout=15)
    dr = requests.delete(f"{BASE_URL}/raffles/{raf_admin}?reason=test", headers=_auth_headers(admin_token), timeout=15)
    ann_default, ann_default_code = _is_in_list(f"{BASE_URL}/guild/announcements", admin_token, ann_admin)
    ann_all, ann_all_code = _is_in_list(f"{BASE_URL}/guild/announcements?include_deleted=true", admin_token, ann_admin)
    evt_default, evt_default_code = _is_in_list(f"{BASE_URL}/guild/events", admin_token, evt_admin)
    evt_all, evt_all_code = _is_in_list(f"{BASE_URL}/guild/events?include_deleted=true", admin_token, evt_admin)
    _print("soft_delete_admin_announcement", da.status_code == 200 and (not ann_default) and ann_all, f"delete={da.status_code} default={ann_default_code} include_deleted={ann_all_code}")
    _print("soft_delete_admin_event", de.status_code == 200 and (not evt_default) and evt_all, f"delete={de.status_code} default={evt_default_code} include_deleted={evt_all_code}")
    _print("soft_delete_admin_raffle", dr.status_code == 200 and dr.json().get("status") == "deleted", f"status={dr.status_code} raffle_status={dr.json().get('status')}")

    ann_leader = _create_announcement(leader_token, f"leader-{suffix}")
    evt_leader = _create_guild_event(leader_token, f"leader-{suffix}")
    raf_leader = _create_raffle(leader_token, f"leader-{suffix}")

    lda = requests.delete(f"{BASE_URL}/guild/announcements/{ann_leader}", headers=_auth_headers(leader_token), json={"reason": "test"}, timeout=15)
    lde = requests.delete(f"{BASE_URL}/guild/events/{evt_leader}", headers=_auth_headers(leader_token), json={"reason": "test"}, timeout=15)
    ldr = requests.delete(f"{BASE_URL}/raffles/{raf_leader}?reason=test", headers=_auth_headers(leader_token), timeout=15)
    l_ann_default, l_ann_default_code = _is_in_list(f"{BASE_URL}/guild/announcements", leader_token, ann_leader)
    l_ann_all, l_ann_all_code = _is_in_list(f"{BASE_URL}/guild/announcements?include_deleted=true", leader_token, ann_leader)
    l_evt_default, l_evt_default_code = _is_in_list(f"{BASE_URL}/guild/events", leader_token, evt_leader)
    l_evt_all, l_evt_all_code = _is_in_list(f"{BASE_URL}/guild/events?include_deleted=true", leader_token, evt_leader)
    _print("soft_delete_leader_announcement", lda.status_code == 200 and (not l_ann_default) and l_ann_all, f"delete={lda.status_code} default={l_ann_default_code} include_deleted={l_ann_all_code}")
    _print("soft_delete_leader_event", lde.status_code == 200 and (not l_evt_default) and l_evt_all, f"delete={lde.status_code} default={l_evt_default_code} include_deleted={l_evt_all_code}")
    _print("soft_delete_leader_raffle", ldr.status_code == 200 and ldr.json().get("status") == "deleted", f"status={ldr.status_code} raffle_status={ldr.json().get('status')}")

    ua = requests.delete(f"{BASE_URL}/guild/announcements/{ann_leader}", headers=_auth_headers(user_token), json={"reason": "test"}, timeout=15)
    ue = requests.delete(f"{BASE_URL}/guild/events/{evt_leader}", headers=_auth_headers(user_token), json={"reason": "test"}, timeout=15)
    ur = requests.delete(f"{BASE_URL}/raffles/{raf_leader}?reason=test", headers=_auth_headers(user_token), timeout=15)
    _print("soft_delete_user_forbidden_announcement", ua.status_code == 403, f"status={ua.status_code}")
    _print("soft_delete_user_forbidden_event", ue.status_code == 403, f"status={ue.status_code}")
    _print("soft_delete_user_forbidden_raffle", ur.status_code == 403, f"status={ur.status_code}")

    # 7) Deleted items hidden from default lists
    la = requests.get(f"{BASE_URL}/guild/announcements", headers=_auth_headers(admin_token), timeout=15)
    le = requests.get(f"{BASE_URL}/guild/events", headers=_auth_headers(admin_token), timeout=15)
    lr = requests.get(f"{BASE_URL}/raffles/", headers=_auth_headers(admin_token), timeout=15)
    ann_ids = {int(item["id"]) for item in la.json()} if la.status_code == 200 else set()
    evt_ids = {int(item["id"]) for item in le.json()} if le.status_code == 200 else set()
    raf_ids = {int(item["id"]) for item in lr.json()} if lr.status_code == 200 else set()
    _print("deleted_hidden_announcements", ann_admin not in ann_ids and ann_leader not in ann_ids, f"status={la.status_code}")
    _print("deleted_hidden_events", evt_admin not in evt_ids and evt_leader not in evt_ids, f"status={le.status_code}")
    _print("deleted_hidden_raffles", lr.status_code == 200 and raf_admin not in raf_ids and raf_leader not in raf_ids, f"status={lr.status_code}")

    # 8) System monitor/admin tools + guild list
    gs_admin = requests.get(f"{BASE_URL}/guild-management/guilds", headers=_auth_headers(admin_token), timeout=15)
    gs_leader = requests.get(f"{BASE_URL}/guild-management/guilds", headers=_auth_headers(leader_token), timeout=15)
    mon = requests.get(f"{BASE_URL}/guild-management/api-monitor", headers=_auth_headers(admin_token), timeout=45)
    sync_status = requests.get(f"{BASE_URL}/admin/sync/status", headers=_auth_headers(admin_token), timeout=15)
    _print("admin_guilds_visible", gs_admin.status_code == 200 and isinstance(gs_admin.json(), list), f"status={gs_admin.status_code} guilds={gs_admin.text[:160]}")
    _print("leader_own_guild_visible", gs_leader.status_code == 200 and "TestGuild" in gs_leader.text, f"status={gs_leader.status_code} guilds={gs_leader.text[:160]}")
    _print("system_monitor_status", mon.status_code == 200 and "apis" in mon.text, f"status={mon.status_code}")
    _print("sync_status_visible", sync_status.status_code == 200 and "active_jobs" in sync_status.text, f"status={sync_status.status_code} body={sync_status.text[:180]}")

    # 9) Local image cache behavior
    creatures = requests.get(f"{BASE_URL}/creatures/?limit=1", timeout=20)
    cache_ok = False
    cache_detail = "creatures list unavailable"
    if creatures.status_code == 200 and creatures.json():
        creature_id = int(creatures.json()[0]["id"])
        img1 = requests.get(f"{BASE_URL}/creatures/{creature_id}/image", timeout=45)
        img2 = requests.get(f"{BASE_URL}/creatures/{creature_id}/image", timeout=45)
        src1 = img1.headers.get("X-Image-Source", "")
        src2 = img2.headers.get("X-Image-Source", "")
        cache_ok = img2.status_code == 200 and src2 in {"local-cache", "stale-cache"}
        cache_detail = f"status1={img1.status_code} src1={src1} status2={img2.status_code} src2={src2}"
    _print("image_cache_local", cache_ok, cache_detail)

    # 10) cleanup script dry-run
    cleanup = subprocess.run(
        ["/forge/.venv/bin/python", "/forge/tibiahub/scripts/cleanup_soft_deleted.py", "--dry-run", "--older-than-days", "0"],
        check=False,
        capture_output=True,
        text=True,
    )
    dry_ok = cleanup.returncode == 0 and "[DRY-RUN]" in cleanup.stdout
    _print("cleanup_dry_run", dry_ok, f"exit={cleanup.returncode} out={cleanup.stdout.splitlines()[:3]}")

    # 11) Runtime CPU/RAM/status snapshot from PM2 (system monitor evidence)
    pm2 = subprocess.run(["pm2", "jlist"], check=False, capture_output=True, text=True)
    pm2_ok = False
    pm2_detail = f"exit={pm2.returncode}"
    if pm2.returncode == 0:
        try:
            data = json.loads(pm2.stdout)
            target = next((p for p in data if p.get("name") == "tibiahub-api"), None)
            if target:
                cpu = target.get("monit", {}).get("cpu")
                mem = target.get("monit", {}).get("memory")
                status = target.get("pm2_env", {}).get("status")
                pm2_ok = status == "online"
                pm2_detail = f"status={status} cpu={cpu} memory={mem}"
        except Exception as exc:
            pm2_detail = f"parse_error={exc}"
    _print("system_monitor_cpu_ram_status", pm2_ok, pm2_detail)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
