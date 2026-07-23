# Guild leadership and recruitment

## Architecture and scope

Leadership is guild-scoped. The own-guild workspace derives the guild from the authenticated user; admin assistance resolves a fixed registered guild key. Clients cannot select an arbitrary guild. `GuildLeadershipRole` is extensible, while this release activates only `viceleader`. Legacy `recruitments` records remain readable and are neither migrated nor deleted.

The normalized model contains roles, openings, applications, immutable application history, audience-filtered messages, interviews, private votes, and assignments. An acceptance records a TibiaHub assignment only. It never changes TibiaData or the character's in-game rank.

## Permission matrix

| Action | Member | Viceleader when enabled | Guild Leader | Global admin assistance |
|---|---:|---:|---:|---:|
| View open opportunities / own application | Yes | Yes | Yes | Yes |
| Submit / reply / withdraw own application | Yes | Yes, unless already assigned | Yes, except leader cannot apply | No |
| View candidates and internal comments | No | Yes | Yes | Yes |
| Comment and vote | No | Yes, when configured | Yes | Yes |
| Configure openings / interviews | No | No | Yes | Yes |
| Accept or reject | No | No | Yes | Yes |
| Mark in-game promotion | No | No | Yes | Yes |

Viceleader review is an opening-level opt-in. No delegated-manager authority is inferred. Admin assistance keeps the admin's membership unchanged and writes `admin_assistance` history plus assisted workspace audits.

## Lifecycles

Openings use `draft -> open -> paused/closed -> archived`; a paused opening can reopen, and a closed opening can reopen or archive. Archived openings are read-only. Closing never deletes applications.

Applications use `applied`, `under_review`, `more_information_requested`, `interview`, `voting`, `accepted`, `rejected`, `withdrawn`, and `cancelled`. The server validates every transition. Accepted/rejected/withdrawn/cancelled are terminal for normal actors. A global-admin override requires a reason and remains audited. Applicants may withdraw only before a final state.

## Privacy, communication, interviews, and voting

Applicants receive only their safe profile snapshot, applicant-visible/both messages, public status history, and interview logistics. Email, internal user IDs, credentials, reviewer comments, vote details, and unrelated profile data are excluded. Reviewers receive submitted answers, internal comments, and aggregate vote totals. Each reviewer has one updatable vote; thresholds never auto-accept.

Interviews are lightweight records containing time, timezone, meeting location, completion state, and reviewer-only notes. No external calendar, email, or Discord action occurs. Notifications are internal and deduplicated; private application notifications go only to the applicant or current guild leader, never all members.

## Acceptance and promotion

Acceptance creates exactly one active assignment per account, role, and guild through the service guard, links it to the immutable application history, and starts with `in_game_promotion_status=pending`. A Guild Leader or assisting global admin must explicitly mark the real in-game promotion complete.

## Deployment

The PostgreSQL foundation baseline includes the leadership tables and partial indexes. Before production:

1. Back up and rehearse against a recent database copy.
2. Run `alembic upgrade head`, then confirm `alembic current` reports `postgres_foundation_20260722 (head)`.
3. Verify the new tables, application privacy, and admin-assisted audit records.
4. Do not seed openings, applications, assignments, or alter legacy recruitment data automatically.

## Mobile manual test checklist

- At 320, 375, 390, 430, 768, and 1024+ px, verify no page-level horizontal overflow.
- Verify full-width fields, 44 px actions, status chips, sticky detail actions, and the application bottom sheet.
- Render member, viceleader-reviewer, leader, and admin-assistance views in English and Spanish.
- Confirm double-tap submit creates one request and unsaved answers trigger leave protection.
- Confirm partial API failures show an inline retry without crashing other guild pages.
- Confirm applicant responses never reveal internal comments or vote totals.
- Confirm the assistance banner and Guild Directory return action persist on admin routes.

## Workspace polish and onboarding

The leadership workspace is organized as a dashboard, recruitment pipeline, and
application detail view. Summary cards expose pending reviews, interviews,
promotion follow-up, and the signed-in member's own application. Application
detail keeps applicant communication separate from reviewer-only notes and
shows a chronological, audience-filtered timeline. Accepted members receive an
explicit onboarding/promotion follow-up state; completing it is an auditable
manager action and duplicate completion is rejected.

All leadership routes are lazy-loaded and render a translated loading state.
API panels use independent loading/error boundaries so one failed request does
not blank the rest of the page. Forms use full-width controls on small screens,
44px touch targets, safe-area spacing, and confirmation for final decisions.
New labels and workflow statuses are available in English and Spanish.

## Future roles

Add a stable role code and translations, then explicitly enable recruitment and permissions. Reserved concepts such as recruiter, raid leader, treasury manager, Discord moderator, and event coordinator must not appear in the UI until their policy and workflow are implemented.
