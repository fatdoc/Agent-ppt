# PPTist source provenance

Official source: https://github.com/pipipi-pikachu/PPTist
Pinned commit: 82ecf10040ca8da67832f173b58d3baf5da59887
Upstream package version: 2.0.0. These identifiers are not interchangeable.
Snapshot copied without nested .git/history, CI, hooks, node_modules or dist.
LICENSE and original README authorship retained. Commercial authorization is being handled separately by the user.

Banana Slides patches: App.vue host bridge; /editor-app/ base and local port;
remove demo/AI API proxy and disable online services; replace standalone header;
hide new-element controls and unsupported animations; disable creation hotkeys;
use installed system fonts rather than 42 MB bundled fonts; remove prepare hook.
Remaining unsupported style controls produce explicit save errors, never silent loss.

Reproduce: npm ci --ignore-scripts; npm run build.

Final patch inventory:
- Removed standalone import/export modules, old header, pptxgenjs/pptxtojson;
  external AI/API service entry points throw locally; file drop/object paste disabled.
- Header exposes host-owned save/export and authorized existing raster replacement.
- No page topology edits/new objects; server rejects unsupported properties.
- ProseMirror transaction-driven input, composition-aware bridge, flush on blur/export,
  hard_break support and plain-text-only paste; table cells use literal text rendering.
- CSP and local-only assets; system fonts; no bundled font binaries.
- Child Vite 6.4.3 and compatible security lock updates; targeted minimatch override.
- READY handshake retry, origin/source/session validation, listener/timer cleanup.
See ../PPTIST_DEPENDENCY_AUDIT.md and ../PPTIST_MVP_STATUS.md for evidence/limits.
