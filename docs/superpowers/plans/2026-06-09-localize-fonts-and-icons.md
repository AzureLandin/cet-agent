# Localize Fonts And Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all external font and icon dependencies from the frontend by serving Font Awesome, Plus Jakarta Sans, and Noto Sans SC directly from local static assets.

**Architecture:** The frontend nginx container will serve all icon and font assets from `frontend/vendor/`. `index.html` will no longer reference Google Fonts, and `styles.css` will define local `@font-face` rules for the fonts currently referenced by the CSS variables.

**Tech Stack:** HTML, CSS, npm font packages, Docker, unittest

---

### Task 1: Add failing regression test for fully localized font assets

**Files:**
- Modify: `backend/tests/test_regressions.py`
- Test: `backend/tests/test_regressions.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_frontend_uses_local_font_assets_only(self):
        index_html = os.path.join(os.path.dirname(BACKEND_DIR), "frontend", "index.html")
        with open(index_html, "r", encoding="utf-8") as f:
            contents = f.read()

        self.assertNotIn("fonts.googleapis.com", contents)
        self.assertNotIn("fonts.gstatic.com", contents)
        self.assertIn("vendor/fontawesome/css/all.min.css", contents)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_regressions.RegressionTests.test_frontend_uses_local_font_assets_only`
Expected: FAIL because `index.html` still references Google Fonts

- [ ] **Step 3: Write minimal implementation**

Remove external Google Fonts tags and switch to local font assets.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_regressions.RegressionTests.test_frontend_uses_local_font_assets_only`
Expected: PASS

### Task 2: Add local font packages and CSS font-face rules

**Files:**
- Create: `frontend/vendor/fonts/plus-jakarta-sans/*`
- Create: `frontend/vendor/fonts/noto-sans-sc/*`
- Modify: `frontend/index.html`
- Modify: `frontend/css/styles.css`

- [ ] **Step 1: Copy local font files**

Install the font packages in a temp npm directory and copy the required `woff2` files into `frontend/vendor/fonts`.

- [ ] **Step 2: Remove external font links**

Delete Google Fonts `preconnect` and stylesheet tags from `frontend/index.html`.

- [ ] **Step 3: Add local @font-face rules**

Declare `Plus Jakarta Sans` and `Noto Sans SC` in `frontend/css/styles.css` using the copied `woff2` files.

### Task 3: Verify localized assets

**Files:**
- Modify: `backend/tests/test_regressions.py`
- Modify: `frontend/index.html`
- Modify: `frontend/css/styles.css`
- Create: `frontend/vendor/fonts/**`

- [ ] **Step 1: Run focused localization test**

Run: `python -m unittest backend.tests.test_regressions.RegressionTests.test_frontend_uses_local_font_assets_only`
Expected: PASS

- [ ] **Step 2: Run full regression suite**

Run: `python -m unittest backend.tests.test_regressions`
Expected: PASS

- [ ] **Step 3: Rebuild frontend container and verify assets**

Run: `docker compose up -d --build frontend`
Expected: frontend container rebuilds successfully
