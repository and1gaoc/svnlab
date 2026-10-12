# SVNLab Design

## 1. Purpose

SVNLab is a local, read-only Subversion repository browser with a GitLab-inspired interface. A user configures one SVN repository in the browser, browses recent commits, opens a revision, and reviews every file diff from that revision on a single page.

The first release deliberately excludes application login, authorization, repository writes, issue tracking, merge requests, CI/CD, and repository administration.

## 2. Approved Product Decisions

- Backend: Python with FastAPI.
- Repository integration: the installed official `svn` command-line client.
- Frontend: native HTML, CSS, and JavaScript without a frontend framework or build step.
- Deployment: a local application listening on `127.0.0.1` by default.
- Credentials: repository URL, SVN username, and SVN password are persisted only in browser `localStorage`. The backend does not persist them and disables SVN authentication caching.
- Visual direction: GitLab-inspired dark header, project sidebar, neutral surfaces, purple interaction color, compact commit metadata, and code-review-style diffs.
- Main layout: classic page navigation. The commit list and commit detail are separate views.

## 3. User Flow

### 3.1 Repository setup

On first launch, the setup page asks for:

- Repository URL, supporting local `file://`, `svn://`, and HTTP(S) URLs accepted by the installed SVN client.
- Username.
- Password.

The user can test the connection. A successful test saves all three values to `localStorage` and opens the commit list. Settings can be changed later from the sidebar.

### 3.2 Commit list

The commit list is ordered newest first and displays 30 entries per page. Each row shows revision, author, time, commit message, and changed-file count. Pagination loads older or newer entries without exposing credentials in the URL.

Selecting a commit navigates to its detail view through a hash route.

### 3.3 Commit detail

The detail page automatically loads and renders the selected revision's metadata, changed-file index, and complete diff for every changed file. No file needs to be clicked to load its diff.

A sticky file index provides anchor navigation within the page. Each file section displays its change status, path, line statistics when available, and complete diff hunks. Binary files, deleted files, copied paths, and property-only changes receive explicit states.

The page has a global display switch:

- Split: old and new versions side by side. This is the desktop default.
- Unified: old and new lines in one stream. This is the automatic narrow-screen mode and can be selected manually.

All file sections switch together.

### 3.4 Context expansion and file content

Diff hunks initially include the normal surrounding context emitted by SVN. Hidden unchanged regions contain controls in the left gutter:

- Expand 20 lines upward.
- Expand 20 lines downward.
- Expand 20 lines in both directions.

Split mode expands corresponding old and new revision content together. A control disappears after reaching the relevant file boundary.

Each file also has a "View file" mode for its content at the selected revision. Content is presented in chunks to avoid creating an excessively large DOM. The backend obtains source with `svn cat`, keeps a bounded in-memory cache, and returns only the requested line range to the browser. This is on-demand context; it does not gate or truncate the revision's complete diff.

## 4. Architecture

### 4.1 Application structure

FastAPI serves both the JSON API and packaged static frontend from the same origin. The backend is divided into:

- API routes: request validation and HTTP response mapping.
- SVN client: constructs fixed argument arrays and runs subprocesses without a shell.
- Parsers: translate SVN XML and unified diff output into stable application models.
- Content cache: a bounded, short-lived in-memory cache for file content fetched by revision and path.
- Static application: hash routing, state, API client, rendering, and local settings.

The browser owns repository connection settings. Every repository API request carries a JSON connection object. The server never writes connection data to disk and never includes it in logs.

### 4.2 SVN commands

- Connection check: `svn info --xml`.
- Commit list and changed paths: `svn log --xml --verbose --limit`.
- Revision metadata: `svn log --xml --verbose -r REV`.
- Complete revision diff: `svn diff -c REV`.
- File content: `svn cat -r REV URL`.

Every command uses `--non-interactive`, `--no-auth-cache`, and explicit credentials when supplied. Commands are passed as argument arrays and are never composed into a shell string. Repository paths and peg revisions are encoded deliberately so an `@` in a path cannot alter revision semantics.

### 4.3 API

All endpoints use POST for operations carrying repository credentials:

- `POST /api/repository/check`
- `POST /api/commits`
- `POST /api/commits/{revision}`
- `POST /api/files/content`
- `GET /api/health`

Commit list requests include page size and an optional upper revision cursor. File-content requests include path, revision, start line, and line count. Credentials are never placed in a query string.

### 4.4 Diff model

The backend parses SVN unified diff output into files and hunks rather than sending HTML. Each hunk contains old/new ranges and typed lines: context, addition, deletion, and metadata. The frontend renders these models as escaped text and derives split or unified rows.

The parser preserves SVN property-change sections and recognizes binary markers. A malformed section produces an explicit raw-text fallback for that file instead of dropping the remainder of the revision.

## 5. Security and Privacy

- The server binds to loopback by default and is not intended for public exposure.
- The API is same-origin and does not enable permissive CORS.
- Repository values are validated for length and supported URL shape.
- Revisions, paging values, paths, and line ranges have strict types and bounds.
- The backend does not use `shell=True`.
- Secrets are redacted from structured errors and application logs.
- SVN authentication caching is disabled.
- Repository-controlled author names, messages, paths, properties, and source lines are rendered as text, never inserted as HTML.
- Because the password is saved in `localStorage`, anyone with access to the browser profile can read it. The setup page states this limitation clearly.
- The password is briefly visible to the local operating system as part of the SVN subprocess command line. This is documented as a limitation of the CLI-based minimal architecture.

## 6. Performance and Failure Behavior

- SVN subprocess concurrency is bounded.
- Connection, log, diff, and content commands have explicit timeouts. Timed-out processes are terminated.
- The commit page loads 30 rows at a time.
- Revision detail makes one metadata request and one complete diff request through a single API operation.
- Large source files are returned to the browser by line range and cached in memory with size and entry limits.
- A loading skeleton remains visible while revision data is fetched.
- A failure in one optional file-content request appears only in that file section and does not clear already loaded revision data.
- API errors distinguish missing SVN CLI, authentication failure, untrusted certificate, unreachable repository, timeout, missing revision/path, binary content, and undecodable content.
- The application does not silently accept invalid TLS certificates. Certificate trust remains governed by the installed SVN client configuration.

## 7. Responsive Behavior and Accessibility

- Desktop uses the project sidebar and split diff by default.
- Narrow layouts collapse the project sidebar and switch diffs to unified mode.
- Controls are keyboard reachable and have visible focus states.
- Status is not communicated by color alone.
- Diff line numbers and source content remain selectable independently where practical.
- Reduced-motion preferences disable nonessential transitions.

## 8. Verification

Automated tests cover:

- SVN XML parsing and unified diff parsing.
- Argument construction, input validation, timeout behavior, and secret redaction.
- FastAPI success and error responses.
- Hash routing, settings persistence, diff row construction, and HTML-safe rendering logic where practical without a browser framework.
- End-to-end backend integration against a temporary local SVN repository, including commit listing, complete multi-file diff, file content, deleted files, and context-range responses.

Manual browser verification covers desktop and narrow layouts, repository setup, pagination, a revision containing multiple files, split/unified switching, sticky file navigation, file-content mode, context expansion, loading states, and error states.

## 9. Delivery

The repository contains application code, tests, dependency metadata, sample environment configuration if needed, and a README with Windows and Linux prerequisites. A development server starts with one documented command after Python dependencies and the SVN CLI are installed.

