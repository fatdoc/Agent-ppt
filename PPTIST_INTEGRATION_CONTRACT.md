# PPTist integration contract

Baseline: 2ce5463f8499707a5f02a63e410f042fa3e4c45c. Branch: codex/pptist-editor-mvp-20260925.
PPTist source: https://github.com/pipipi-pikachu/PPTist at 82ecf10040ca8da67832f173b58d3baf5da59887, upstream package 2.0.0. Source snapshot and LICENSE are in editor-pptist; commercial authorization is handled by the user separately.

## Ownership and model

React remains the host at `/project/:projectId/editor`, lazy loaded from Preview. Vue builds independently at `/editor-app/`; iframe is engineering isolation, not a security boundary. Shared bridge is `shared/pptistProtocol.ts`. React owns navigation, dirty/saved state, history, task admission and result links. PPTist owns thumbnails, canvas, undo, selection and properties.

Authoritative data is semantic Page schema 1.0. Python `PPTistAdapter` implements the existing EditorAdapter protocol structurally, without modifying semantic_export core. Editor JSON is derived and never accepted as authoritative provenance. Service-side base revision preserves IDs/source/revision/assets/provenance/corrections. Existing native text/shape/image/SVG/table edits are mapped; active/unsupported rich HTML fails before storage. HTML is regenerated from escaped runs. Tables are rendered as literal text in patched Vue components.

Supported: Chinese runs, paragraphs/soft breaks, solid backgrounds, four schema shapes, existing authorized images and SVG with PNG fallback, rectangular table cell text/column widths, absolute move/resize/rotation and identity grouping/ungrouping/contiguous ordering. Screenshot whole-image ratio/crop rules and page bounds are revalidated through AssetStore/Page. No-op adapter roundtrip preserves exact original model. Rich-text DOM canonicalization alone does not merge authoritative runs.

Not enabled: new/copied objects (explicit semantic origin absent), new/copied/deleted/reordered slides, nested groups, native lines, table row/column insertion/merge/per-cell style changes, arbitrary SVG/path/gradient/background image, animation, notes, media, PPTX/private JSON import and standalone PPTist export. Unsupported controls that remain in upstream inspector cause an explicit save error and keep the draft; they are not silently dropped. Nested-group documents are read-only on GET. New-element toolbar/creation shortcuts, page controls/drag and animation tabs are hidden/disabled. Only validated structured documents can initialize; image-only projects get a truthful unavailable state. OCR/automatic reconstruction is not implemented.

## Bridge

`banana-pptist/1`: READY, LOAD_DOCUMENT, DOCUMENT_CHANGED, SAVE_RESULT, REQUEST_EXPORT, ERROR. Exact origin + iframe/parent Window source + random session + protocol version + object envelope + <=4 MiB checks. Host accepts READY once per mounted session, loads once, accepts monotonically increasing change sequences only after handshake. Listeners and debounce timers are removed on unmount. Reload/retry makes a new session; expired-session messages fail. No Provider key is sent.

Load payload: slides, width, height, revision, asset_options and optional fixture flag. Change: slides and sequence. Save-result: sequence, ok, revision/message. REQUEST_EXPORT flushes rich text and current slides; composition in progress refuses export. Debounced edits are held while composition is active. SAVE_RESULT only announces server-confirmed persistence.

## Storage and authorization

Migration `031_pptist_editor_documents` → `030_batch01_safety_expand`, single head. `editor_documents(project_id PK/FK, revision > 0)` and `editor_revisions(uuid PK, project_id FK, revision > 0, payload, actor_user_id FK, restored_from_revision, created_at)`, unique project/revision. No modification to existing Page/Task schema.

All routes are under authenticated editor blueprint, and reuse Cookie/CSRF/access-code/single-user gate/project ownership. Only after authentication and CSRF, app binds an owner-scoped empty ProviderConfigSnapshot for this exact blueprint; all others keep original behavior. Empty snapshot is not a network sandbox. Editor code never calls Provider factories/SDKs; isolated tests block network and spy on OAuth/factories. React's existing AuthGuard and other non-editor API endpoints are unchanged and may still capture Provider settings/OAuth; this exception is deliberately narrow.

- GET `/api/projects/:id/editor-document`: revision, semantic pages, editor slides, dimensions and authorized asset choices. Missing = 404 EDITOR_DOCUMENT_NOT_FOUND, no fake conversion. Unsupported imported content returns readonly + reason.
- POST `.../editor-document/initialize`: `{base_revision:0,pages:[Page...]}` only; cannot overwrite existing documents. Local Page IDs/order must match project. Trusted server root comes from UPLOAD_FOLDER and the authorized Project, never from client data.
- PUT `.../editor-document`: `{base_revision,slides}`; no Page/source metadata override. SQL conditional update `WHERE project_id AND revision=base_revision`, then snapshot insert/response validation in same transaction. CAS miss/duplicate initialization = 409 EDITOR_REVISION_CONFLICT. Other integrity errors are not relabeled as conflicts.
- GET `.../editor-document/revisions`: newest 100 metadata records.
- POST `.../editor-document/restore`: `{base_revision,revision}`; same CAS, new revision and actor/restored-from audit, never rewrite history.
- GET `.../editor-assets/:asset_id?sha256=...`: project owner + membership in an authorized historical revision + hash + MIME/nosniff/SVG validation. Assets initialized through API are frozen at content-addressed `editor-assets/<sha>.<ext>`. Later edits select authorized membership and never overwrite old paths. Missing/corrupted assets fail closed.

Limits: 4 MiB document envelope/response; 100 pages; 1,000 objects/page; 20 MiB per asset. Unsupported changes = 400; excess envelope = 413; cross-project = 404. Filename paths never enter semantic payloads. Snapshot assets/DB are not committed.

Single save in flight; new edits remain pending until the acknowledged revision becomes next base. 409/network failures keep in-memory draft; manual save and draft JSON download are available. Before-unload and explicit Back warn on dirty content. Draft is not a server save; closing after accepting the warning loses in-memory state. History restore requires a clean editor and creates a new revision.

## Export

POST `.../editor-document/export` `{revision}` admits Task `EXPORT_SEMANTIC_EDITOR`, status PENDING→PROCESSING→COMPLETED/FAILED. Per-project serialized admission returns the active same-revision task on duplicate clicks; another revision while active gets 409. Explicit owner-scoped empty snapshot + TaskExecutionContext(deadline 300 seconds) go to TaskManager. No AI construction, no credit reservation/debit. Worker binds immutable revision UUID/project/hash, validates authorized assets, makes deterministic PageJobs and invokes existing export_jobs/checkpoints. Editing later revisions cannot affect the snapshot.

Checkpoints currently task-scoped; no cross-retry-task reuse. Staging uses hidden `.editor-staging`, never public exports. After OOXML audit and last cancellation check, atomic replace publishes task/revision-specific filename; then worker writes COMPLETED/time/result. Submission failure becomes FAILED. GET/DELETE `.../editor-document/export-tasks/:task` polls/requests cooperative cancellation. GET `.../editor-document/exports/:task` requires owner/project/task type/COMPLETED and avoids non-editor OAuth capture. Existing export task store/panel recognizes semantic-editor.

Original image export, Provider architecture, AI candidate generation and legacy Page image histories remain independent. AI output does not write editor revisions; automatic candidate-version UI is not implemented.

## Production build / rollback

`npm ci --ignore-scripts` in editor-pptist; `node scripts/build_pptist_editor.mjs`; then frontend `npm run build:check`. Dockerfile builds editor separately and copies `/editor-app/` before React build; nginx uses a specific static path and CSP. Docker image has not been built or deployed in this task.

Deploy only after coordinator review, backup and established migration procedure; no real DB migration was run. Revert feature commit to remove routes/UI; downgrade 031 drops editor revision history, so back it up and do not downgrade live without explicit operational authorization. Existing Local Pages are never deleted by this MVP.
