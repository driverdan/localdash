## ADDED Requirements

### Requirement: Admin feature namespace
The frontend SHALL provide an `admin` feature under `frontend/src/features/admin/` whose
`index.ts` exports the admin dashboard page. It SHALL obtain the signed-in user and log-out
only through the auth feature's `index.ts`.

#### Scenario: Admin depends on auth's public surface only
- **WHEN** the admin feature's imports are inspected
- **THEN** they resolve to its own files, `frontend/src/lib/`, third-party packages, or `frontend/src/features/auth/index.ts`

### Requirement: The admin route is limited to admins
The `/admin` route SHALL render the admin dashboard page only when the signed-in user is an
admin. While the signed-in user state is `unknown` it SHALL show a loading indication and
SHALL NOT render the dashboard or redirect. An anonymous visitor SHALL be redirected to
`/login` without adding a history entry. A signed-in user who is not an admin SHALL see a
message that they do not have access, with a log-out control, and SHALL NOT see the dashboard.

#### Scenario: Anonymous visitor is sent to login
- **WHEN** a visitor without a session opens `/admin`
- **THEN** the URL becomes `/login`, the login page renders, and pressing Back does not return to `/admin`

#### Scenario: Admin sees the dashboard
- **WHEN** a signed-in admin opens `/admin`
- **THEN** the admin dashboard page renders

#### Scenario: Non-admin is refused
- **WHEN** a signed-in user who is not an admin opens `/admin`
- **THEN** a no-access message with a log-out control renders and the dashboard does not

#### Scenario: No flash before the check completes
- **WHEN** `/admin` is opened and the signed-in user check has not finished
- **THEN** a loading indication is shown and neither the dashboard nor the login page renders

### Requirement: Admin dashboard page
The admin dashboard page SHALL show a heading, the signed-in user's email and a log-out
control, and no other content. It SHALL be styled with the existing design tokens so that it
follows the selected theme without per-theme rules, and SHALL render the shared site footer
after its content.

#### Scenario: Shows who is signed in
- **WHEN** an admin with email `admin@example.com` views the dashboard
- **THEN** the page shows a heading, `admin@example.com` and a log-out control

#### Scenario: Log-out from the dashboard
- **WHEN** the admin activates the log-out control
- **THEN** the session is ended, the URL becomes `/login`, and opening `/admin` again redirects to `/login`

#### Scenario: Footer is present
- **WHEN** the dashboard is rendered
- **THEN** the shared site footer appears after its content
