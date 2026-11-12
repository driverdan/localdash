## ADDED Requirements

### Requirement: Auth feature namespace
The frontend SHALL provide an `auth` feature under `frontend/src/features/auth/`, matching the
`/api/v1/auth` API namespace. Its `index.ts` SHALL be its only public surface, exporting the
login page, the signed-in user state, and the functions that load the user and log out.

#### Scenario: Other code uses only the public surface
- **WHEN** the shell or the admin feature needs the login page, the signed-in user or log-out
- **THEN** it imports them from `frontend/src/features/auth/index.ts` and from no other file in the feature

### Requirement: Signed-in user state is loaded lazily
The auth feature SHALL hold the signed-in user as reactive state with three statuses:
`unknown` (not yet checked), `anonymous` and `signedIn` (with the user's id, email and admin
flag). It SHALL determine the status by calling `GET /api/v1/auth/me` at most once per page
load until the status changes through login or log-out, treating a `401` as `anonymous`. The
request SHALL be made only when the `/login` or `/admin` route is rendered.

#### Scenario: Public pages make no auth request
- **WHEN** a visitor loads `/`, `/news`, `/map` or `/events` and never opens `/login` or `/admin`
- **THEN** no request is made to `/api/v1/auth/me`

#### Scenario: Signed-in user is recognised
- **WHEN** a browser holding a valid session cookie opens `/admin`
- **THEN** one request is made to `/api/v1/auth/me` and the status becomes `signedIn` with that user's email and admin flag

#### Scenario: Missing session is anonymous
- **WHEN** a browser without a valid session cookie opens `/login`
- **THEN** the `401` from `/api/v1/auth/me` sets the status to `anonymous` and no error is shown

### Requirement: Login page
The auth feature SHALL provide a login page with an email input, a password input and a
submit button. Submitting SHALL post the email (as `username`) and the password to
`POST /api/v1/auth/login` as form-encoded data. The inputs SHALL carry `autocomplete`
attributes (`username` and `current-password`) so password managers can fill them. The submit
button SHALL be disabled while a request is in flight. The session token SHALL NOT be read,
stored or sent by page JavaScript; the browser's cookie handling carries it.

#### Scenario: Successful login
- **WHEN** a user submits a correct email and password
- **THEN** the page reloads the signed-in user state, which becomes `signedIn`

#### Scenario: Wrong credentials
- **WHEN** the login request returns `401`
- **THEN** the page shows "Incorrect email or password", stays on the form, and keeps the email input's value

#### Scenario: Other failure
- **WHEN** the login request fails with a network error or a status other than `204` or `401`
- **THEN** the page shows a generic could-not-sign-in message and the form can be submitted again

#### Scenario: Double submit is prevented
- **WHEN** a login request is in flight
- **THEN** the submit button is disabled until the request settles

### Requirement: Log-out
The auth feature SHALL provide a log-out function that calls `POST /api/v1/auth/logout` and
then sets the signed-in user state to `anonymous`.

#### Scenario: Log-out clears the state
- **WHEN** a signed-in user logs out
- **THEN** the log-out endpoint is called and the status becomes `anonymous`

### Requirement: Login page presentation
The login page SHALL be styled with the existing design tokens so that it follows the selected
theme without per-theme rules, SHALL be usable at mobile width, and SHALL render the shared
site footer after its content.

#### Scenario: Follows the theme
- **WHEN** the login page is viewed in the default theme and in the dark theme
- **THEN** its text, inputs and button are legible in both

#### Scenario: Footer is present
- **WHEN** the login page is rendered
- **THEN** the shared site footer appears after the form
