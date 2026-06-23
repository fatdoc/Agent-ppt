# PPT to PPT Design Spec

**Date:** 2026-05-23

**Status:** Draft

**Owner Intent:** Use an excellent existing PPT as a reference for form, style, layout rhythm, and narrative expression, then generate a new PPT for the user's own competition project, work report, pitch, or other content.

---

## 1. Product Definition

PPT to PPT is not ordinary PPT renovation.

Existing PPT renovation means: upload an old PPT/PDF, parse its original content, and regenerate or polish that same deck.

PPT to PPT means: upload a reference PPT that the user admires, extract its reusable design and storytelling patterns, combine those patterns with the user's new project/work content, and generate a new deck whose content belongs to the user while its presentation form feels inspired by the reference.

In one sentence:

> "I saw a great deck. Help me make my own deck with a similar structure, visual language, page rhythm, and descriptive style, but with my own topic and materials."

---

## 2. Target Users And Scenarios

### 2.1 Users

- Competition teams that want to learn from award-winning pitch decks or roadshow decks.
- Employees preparing work reports, strategy reports, quarterly reviews, or project summaries.
- Students preparing defense slides, course reports, or innovation project presentations.
- Founders or product managers who have strong reference decks but weak slide design capacity.

### 2.2 Core Scenarios

- "I found a winning competition PPT. Generate a deck for my own project with the same level of storytelling and visual quality."
- "I like this consulting-style work report. Turn my messy project notes into a similar report deck."
- "This PPT has great title phrasing, section rhythm, and page layouts. Use it as a style blueprint for my own topic."
- "Keep the same overall design taste, but do not copy the original content, charts, data, logo, or proprietary text."

---

## 3. User Experience

### 3.1 Entry Point

Add a new homepage creation mode:

**PPT to PPT**

Recommended Chinese label:

**借鉴优秀 PPT 生成**

Recommended subtitle:

**上传一份参考 PPT，再输入你的项目内容，AI 会学习它的结构、风格和表达方式，生成你的新 PPT。**

This should be separate from **PPT 翻新**. The two modes solve different problems:

| Mode | User goal | Reference content | Output content |
| --- | --- | --- | --- |
| PPT 翻新 | Improve or rebuild the uploaded deck | Original deck is the source content | Same or polished content |
| PPT to PPT | Create a new deck inspired by a reference deck | Original deck is style/structure reference | User's new topic/content |

### 3.2 Required Inputs

The first version should require:

1. **Reference PPT/PDF file**
   - Supported formats: `.pptx`, `.ppt`, `.pdf`
   - Used to extract style, page structure, layout rhythm, and expression patterns.
2. **User content**
   - Could be a topic, project description, outline, report notes, or pasted source material.
   - Must be treated as the source of truth for new deck content.

### 3.3 Optional Inputs

- Desired page count. Default: follow the reference deck page count when reasonable.
- Output language. Default: current app setting.
- Match strength:
  - `loose`: learn general style and structure.
  - `balanced`: preserve section rhythm and common page patterns.
  - `strict`: closely follow page count, page roles, and layout patterns, while replacing content.
- Extra requirements:
  - Example: "更像商业计划书", "突出技术创新", "减少文字", "适合 5 分钟路演".
- Reference extraction scope:
  - `style_only`: colors, typography impression, design language.
  - `structure_and_style`: section rhythm, page roles, layout patterns, style.
  - `full_blueprint`: structure, style, page-by-page layout mapping, title expression style.

### 3.4 Happy Path

1. User opens **PPT to PPT**.
2. User uploads a reference PPT/PDF.
3. User enters their own competition/project/work content.
4. User chooses match strength and optional page count.
5. Backend creates a project and an async analysis task.
6. The task renders the reference deck into page images, parses text where possible, and extracts a reusable blueprint.
7. AI generates a new outline and page descriptions from the user's content using the blueprint.
8. User lands in the detail editor with generated page descriptions.
9. User generates images, edits pages, and exports PPTX or editable PPTX.

---

## 4. Functional Requirements

### 4.1 Reference Deck Analysis

The system must analyze the uploaded reference deck into a structured blueprint.

Blueprint fields:

```json
{
  "deck_summary": "What kind of deck this is and what it is optimized for",
  "style_profile": {
    "color_palette": "Main colors, accent colors, background treatment",
    "typography": "Font impression, hierarchy, weight, title/body relationship",
    "visual_language": "Shapes, icons, charts, photos, illustrations, decoration style",
    "mood": "Professional, energetic, academic, futuristic, playful, etc.",
    "layout_tendencies": "Common alignment, spacing, density, composition style"
  },
  "narrative_profile": {
    "section_flow": ["Opening", "Problem", "Solution", "Evidence", "Plan", "Closing"],
    "title_style": "How slide titles are phrased",
    "argument_style": "How claims, evidence, and conclusions are organized",
    "density_style": "Sparse, balanced, dense, report-like"
  },
  "page_patterns": [
    {
      "reference_page_index": 1,
      "page_role": "cover",
      "layout_pattern": "Large title, subtitle, logo/date area, strong background visual",
      "content_pattern": "Project name plus one-line positioning",
      "visual_pattern": "Full-page image or abstract background with restrained accent"
    }
  ],
  "constraints": [
    "Do not reuse original text as new content",
    "Do not copy logos, private data, watermarks, or copyrighted illustrations",
    "Use the reference as inspiration, not as direct reproduction"
  ]
}
```

The blueprint should be stored as project-level metadata or a related analysis artifact so it can be reused for regeneration.

### 4.2 User Content Transformation

The system must treat the user's provided content as authoritative.

It should:

- Extract the user's core topic, project name, audience, goals, key claims, evidence, data, and desired outcome.
- Generate an outline that maps user content into the reference deck's narrative rhythm.
- Produce page descriptions that include actual slide body content, not only visual instructions.
- Avoid importing the reference deck's original factual content unless the user explicitly includes it in their own content.

### 4.3 Page Mapping

The system should support three mapping modes:

| Mode | Behavior | MVP priority |
| --- | --- | --- |
| Reference page count | New deck follows reference page count and page roles | High |
| User page count | New deck uses user-selected page count but borrows reference patterns | High |
| Hybrid | System compresses or expands the reference flow based on content volume | Medium |

For MVP, page mapping can be deterministic:

1. Extract page roles from reference deck.
2. Generate new outline with the same number of pages unless the user specifies otherwise.
3. Assign each generated page a matching reference page pattern.
4. Insert layout/style guidance from that pattern into each page description.

### 4.4 Visual Generation Guidance

For each new page, image generation should receive:

- User's new slide content.
- Deck-level style profile.
- Matched reference page pattern.
- Optional reference page image as a layout/style reference.
- Explicit instruction to avoid copying logos, text, charts, or proprietary assets from the reference.

This should integrate with the existing `VisualGuidanceService` rather than creating a completely separate image prompt system.

### 4.5 Output

The output project should behave like normal Banana Slides projects:

- Detail editor supports page-level editing.
- Slide preview supports image generation and regeneration.
- Existing export options remain available:
  - PPTX as image-based slides.
  - PDF.
  - Images.
  - Editable PPTX beta.

---

## 5. Non-Goals For MVP

MVP should not promise:

- Exact pixel-perfect cloning of the reference deck.
- Copying master slides, animations, transitions, embedded media, or speaker notes.
- Reusing the reference deck's original logos, copyrighted illustrations, or private data.
- Fully editable vector reconstruction of the reference template.
- Automatic chart data reconstruction from the reference deck.

These can become later enhancements after the core workflow works reliably.

---

## 6. Proposed Architecture

### 6.1 New Creation Type

Add a new creation type:

```text
ppt_to_ppt
```

This is separate from:

```text
ppt_renovation
```

Reason:

- `ppt_renovation` parses original content and regenerates that same deck.
- `ppt_to_ppt` analyzes a reference deck and generates a new deck from user content.

### 6.2 Backend Flow

Proposed endpoint:

```http
POST /api/projects/ppt-to-ppt
Content-Type: multipart/form-data
```

Form fields:

| Field | Required | Description |
| --- | --- | --- |
| `reference_file` | Yes | Reference `.pptx`, `.ppt`, or `.pdf` |
| `content` | Yes | User's new project/work/competition content |
| `content_type` | No | `idea`, `outline`, `notes`, or `document_text`; default `notes` |
| `match_strength` | No | `loose`, `balanced`, `strict`; default `balanced` |
| `page_count` | No | Desired number of output pages |
| `language` | No | Output language |
| `extra_requirements` | No | User constraints |

Response:

```json
{
  "project_id": "uuid",
  "task_id": "uuid",
  "reference_page_count": 12
}
```

Async task type:

```text
PPT_TO_PPT_ANALYSIS
```

Task phases:

1. Save reference file.
2. Convert PPT/PPTX to PDF when needed.
3. Render PDF into page images.
4. Parse reference text where possible.
5. Extract deck-level style profile.
6. Extract narrative profile and page patterns.
7. Generate new outline from user content plus blueprint.
8. Generate page descriptions from outline plus blueprint.
9. Save pages and mark project as `DESCRIPTIONS_GENERATED`.

### 6.3 Suggested Services

Create focused services rather than expanding `task_manager.py` further.

| File | Responsibility |
| --- | --- |
| `backend/services/ppt_to_ppt/reference_renderer.py` | Save uploaded reference files, convert to PDF, render page images |
| `backend/services/ppt_to_ppt/blueprint_service.py` | Analyze reference deck into style/narrative/page-pattern blueprint |
| `backend/services/ppt_to_ppt/generation_service.py` | Generate new outline and descriptions from user content and blueprint |
| `backend/services/ppt_to_ppt/data_models.py` | Typed dataclasses for blueprint, page patterns, and options |
| `backend/controllers/ppt_to_ppt_controller.py` | Multipart endpoint and validation |
| `backend/services/task_manager.py` | Thin async task entry point only |

This keeps the workflow understandable and avoids adding another large block to `project_controller.py`.

### 6.4 Reused Existing Capabilities

| Existing capability | How PPT to PPT uses it |
| --- | --- |
| PPT/PDF upload and conversion from `create_ppt_renovation_project` | Reuse file validation, LibreOffice conversion, and PDF rendering logic |
| `FileParserService` | Parse reference page text and uploaded user content files later |
| `get_style_extraction_prompt()` | Starting point for deck/page style extraction |
| `generate_layout_caption()` | Starting point for page layout pattern extraction |
| `InputGenerationService` | Reuse outline/description generation patterns where possible |
| `VisualGuidanceService` | Inject extracted style and page pattern into image prompts |
| Existing export services | Export generated deck without a new export system |

---

## 7. Data Model

### 7.1 Project

Extend allowed `Project.creation_type` values:

```text
idea | outline | descriptions | no_think | ppt_renovation | ppt_to_ppt
```

For MVP, existing fields can store:

- `idea_prompt`: user's new content summary or raw notes.
- `template_style`: extracted deck-level style profile as text.
- `description_text`: generated page descriptions.
- `outline_text`: generated outline.

Recommended later migration:

```text
ppt_to_ppt_blueprint JSON column or related table
```

The blueprint is structured enough that storing it only as plain text will make regeneration and debugging harder.

### 7.2 Page

Each generated page should store:

- Normal outline content.
- Normal description content.
- Optional metadata:
  - matched reference page index.
  - reference page role.
  - extracted layout pattern.
  - extracted visual pattern.

For MVP, this metadata can be embedded in the page description as short fields:

```text
Reference Page Pattern: ...
Layout: ...
Visual Elements: ...
Style Guidance: ...
```

Later, move it into structured page metadata.

---

## 8. Prompting Strategy

### 8.1 Blueprint Extraction Prompt

The blueprint extraction prompt should ask the model to analyze the reference deck as a reusable design system:

- What is the deck for?
- What is the section flow?
- What page roles appear?
- How are titles written?
- How dense is each page?
- What visual motifs repeat?
- What layout patterns repeat?
- Which parts must not be copied?

It should output strict JSON so the next generation step can consume it.

### 8.2 New Content Generation Prompt

The generation prompt should combine:

- User's content.
- Extracted blueprint.
- Match strength.
- Desired page count.
- Language.
- Safety/copyright constraints.

Key instruction:

> Use the reference deck as a pattern library. Do not copy its original claims, data, names, logos, visual assets, or proprietary wording. Generate a new deck whose content is based on the user's material.

### 8.3 Page Description Prompt

Each page description should include:

- Slide title.
- Actual display text.
- Suggested chart/table/list structure when useful.
- Layout pattern derived from matched reference page.
- Visual elements guidance.
- Style guidance inherited from deck profile.

The current Banana Slides import/export description format should be preserved:

```markdown
**Page Description:**
--- 页面文字 ---

### Slide Title

- User-specific point 1
- User-specific point 2

--- 页面文字结束 ---

Visual Elements: ...
Visual Focus: ...
Layout: ...
Style Guidance: ...
```

---

## 9. Frontend Behavior

### 9.1 Home Page

Add a visible tab or mode for **PPT to PPT**.

Fields:

- Reference PPT/PDF upload.
- Main content textarea.
- Match strength segmented control.
- Page count selector.
- Extra requirements textarea.
- Language follows app settings unless overridden.

The UI should make the distinction clear:

- Reference PPT: "用来学习形式和风格"
- Your content: "用来生成新 PPT 的真实内容"

### 9.2 Loading State

After submit, navigate to the detail editor with skeleton pages and task progress.

Progress messages:

- Uploading reference deck.
- Rendering reference pages.
- Analyzing style and structure.
- Mapping your content.
- Writing new page descriptions.
- Ready for editing.

### 9.3 Editor

Generated pages should look like regular description-generated pages.

Each page may show a small reference indicator:

```text
Inspired by reference page 3: Problem analysis page
```

This can be deferred if it slows MVP.

---

## 10. Error Handling

| Failure | Expected behavior |
| --- | --- |
| Unsupported file type | Return validation error before creating project |
| PPT to PDF conversion fails | Ask user to upload PDF version |
| Some reference pages fail rendering | Continue if at least one page renders; warn user |
| Blueprint extraction fails | Mark task failed with retry option |
| User content too short | Return validation error: ask for project/topic/material |
| Generated outline is empty | Fail task with model-output error |
| Image generation ignores style | Allow user to regenerate with stricter match strength or edited style guidance |

The system should avoid silently falling back to generic PPT generation because that breaks the core promise of PPT to PPT.

---

## 11. Privacy, Copyright, And Safety

The feature should position the reference deck as inspiration and analysis input, not as content to copy.

Rules:

- Do not reuse original slide text as generated content unless it appears in the user's provided content.
- Do not preserve original logos, names, watermarks, people, private data, or proprietary charts.
- Do not promise exact cloning.
- Generated descriptions should be phrased as "similar style", "similar layout rhythm", or "inspired by", not "copy".
- If the reference deck contains obvious confidential markings, the UI should remind the user to confirm they have permission to use it as a reference.

---

## 12. MVP Scope

MVP should deliver:

- New PPT to PPT creation mode.
- Upload reference PPT/PDF.
- Enter user content.
- Analyze deck-level style, narrative flow, and page patterns.
- Generate outline and page descriptions for the user's content.
- Use extracted style/page pattern during image generation.
- Export through existing PPTX/PDF/editable PPTX flows.

MVP does not need:

- Perfect template reconstruction.
- Master-slide extraction.
- Animation preservation.
- Interactive reference-page mapping UI.
- Batch comparison across multiple reference decks.

---

## 13. Future Enhancements

### 13.1 Reference Page Mapping UI

Let users manually map:

- My page 1 uses reference page 1.
- My page 2 uses reference page 4.
- My summary page uses reference page 10.

### 13.2 Multi-Reference Blending

Allow users to upload:

- One deck for narrative structure.
- One deck for visual style.
- One deck for chart style.

### 13.3 Style Strength Controls

Per-page controls:

- More like reference.
- More original.
- More business.
- More visual.
- Less text.

### 13.4 Editable Template Extraction

Attempt to extract reusable editable components from the reference deck:

- Color tokens.
- Typography hierarchy.
- Common layout grids.
- Reusable chart/table styles.

This should build on the editable PPTX export and image editability services, but it is not MVP.

---

## 14. Testing Strategy

### 14.1 Unit Tests

- Validate PPT to PPT request options.
- Ensure creation type `ppt_to_ppt` is accepted.
- Test blueprint schema parsing and fallback validation.
- Test page-count mapping rules.
- Test prompts include anti-copy constraints.

### 14.2 Integration Tests

- Upload a small PDF reference and user content.
- Verify project is created with `creation_type=ppt_to_ppt`.
- Verify task creates pages with outline and description content.
- Verify task status reaches `DESCRIPTIONS_GENERATED`.

### 14.3 Frontend Tests

- User can select PPT to PPT mode.
- Submit is blocked without a reference file.
- Submit is blocked without user content.
- Submit calls `/api/projects/ppt-to-ppt`.
- Detail editor shows task progress.

### 14.4 Manual QA

Use three references:

- Competition pitch deck.
- Corporate work report.
- Academic defense deck.

For each, verify:

- New deck content is based on user input.
- Visual style resembles the reference.
- Page roles follow the reference rhythm.
- Original reference text/logos/data are not copied.
- Exported PPTX opens normally.

---

## 15. Acceptance Criteria

The feature is acceptable when:

- A user can upload a reference PPT/PDF and enter their own project/work content.
- The system generates a new project, not a renovation of the old deck.
- Generated pages contain user-specific content.
- Generated page descriptions include style/layout guidance derived from the reference deck.
- The workflow reaches the existing detail editor and export flow.
- The system clearly distinguishes PPT to PPT from PPT renovation in UI and docs.
- Tests cover validation, project creation, task generation, and prompt safety constraints.

---

## 16. Open Decisions

The following decisions should be made before implementation:

1. Should MVP expose `match_strength`, or default to `balanced` and hide the control?
2. Should blueprint be stored in a new JSON column/table now, or embedded in existing text fields for first iteration?
3. Should generated images use the actual reference page image as an image reference, or only use extracted text guidance first?
4. Should PPT to PPT accept multiple user source files in MVP, or only pasted text plus existing reference file support later?

Recommended MVP answers:

1. Expose `match_strength` because it directly matches user expectations.
2. Store blueprint as JSON from the start if migration cost is acceptable.
3. Use extracted text guidance first; add reference image conditioning after validating model behavior.
4. Start with pasted text; reuse reference files in a follow-up.
