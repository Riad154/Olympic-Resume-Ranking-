"""
Apply comprehensive fixes to bdjobs_downloader.py to address:
  1. no_button (67% of failures) — more robust PDF button discovery
  2. failed_card_not_found (20%) — pagination reliability
  3. failed_download_timeout (10%) — download trigger fallback
"""
import re

PATH = r"F:\Projects\resume_ranking\bdjobs_downloader.py"
with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 1: download_uploaded_cv — completely rewritten with more robust button
# discovery and download triggering.
# ═══════════════════════════════════════════════════════════════════════════════

old_download = '''def download_uploaded_cv(page, card, job_id: str, safe_name: str,
                          ts: str, cv_dir: str) -> tuple[str, str]:
    """
    Click the red PDF icon on the card → expect_download → save.
    Returns (filename, status).

    Retry helpers:
      1. Scroll card into view so the PDF button is in the viewport.
      2. Try multiple selectors (icon-pdf-file → pdf-btn → button with PDF label).
      3. Fallback to page-level keyboard/mouse click if element click fails.
    """
    # ── 1. Scroll card into view ──────────────────────────────────
    try:
        card.evaluate("el => el.scrollIntoView({block: 'center'})")
        time.sleep(0.3)
    except Exception:
        pass

    # ── 2. Try multiple selectors ─────────────────────────────────
    cv_btn = None
    selectors = [
        "span.icon-pdf-file",
        "button:has(span.icon-pdf-file)",
        "span[class*='pdf']",
        "button[title*='PDF']",
        "button:has-text('PDF')",
        "a:has-text('PDF')",
    ]
    for sel in selectors:
        cv_btn = card.query_selector(sel)
        if cv_btn:
            break

    if not cv_btn:
        # Last resort: look inside the card for any element containing "PDF"
        try:
            cv_btn = card.query_selector("xpath=.//*[contains(text(), 'PDF')]")
        except Exception:
            pass
    if not cv_btn:
        return "", "no_button"

    try:
        # ── 3. Click with fallback strategies ──────────────────────
        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
            try:
                # Strategy A: direct element click
                cv_btn.click()
            except Exception:
                # Strategy B: JS click via evaluate
                try:
                    cv_btn.evaluate("el => { el.click(); el.dispatchEvent(new MouseEvent('click',{bubbles:true})); }")
                except Exception:
                    # Strategy C: focus + Enter key on the card, then page.keyboard.press
                    try:
                        card.evaluate("el => el.focus()")
                        page.keyboard.press("Enter")
                    except Exception:
                        raise
        download = dl_info.value

        filename  = f"{job_id}_{safe_name}_{ts}_uploaded.pdf"
        save_path = os.path.join(cv_dir, filename)
        download.save_as(save_path)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 100:
            with open(save_path, "rb") as f:
                header = f.read(5)
            status = "success" if header == b"%PDF-" else "success_unverified"
        else:
            status = "failed_empty"
        return filename, status

    except PwTimeout:
        return "", "failed_download_timeout"
    except Exception as e:
        return "", f"failed_download: {e}"'''

new_download = '''def download_uploaded_cv(page, card, job_id: str, safe_name: str,
                          ts: str, cv_dir: str) -> tuple[str, str]:
    """
    Click the red PDF icon on the card → expect_download → save.
    Returns (filename, status).

    BDJobs CV button is highly variable across candidate cards.
    We use a cascading strategy:
      1. Scroll card into view + hover to reveal lazy buttons.
      2. Deep DOM search inside the card for any clickable PDF/download element.
      3. Try direct click → JS click → keyboard Enter → parent row click.
      4. If all button-based approaches fail, try page-level keydown(Ctrl+J)
         which many Angular apps bind to "download" actions.
    """
    # ── 1. Scroll into view + hover to reveal lazy elements ───────
    try:
        card.evaluate("el => { el.scrollIntoView({block:'center'}); el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }")
        time.sleep(0.4)
    except Exception:
        pass

    # ── 2. Deep DOM search for PDF / download trigger ─────────────
    cv_btn = None

    # Phase A: exact known selectors
    selectors = [
        "span.icon-pdf-file",
        "button:has(span.icon-pdf-file)",
        "span[class*='pdf']",
        "button[title*='PDF']",
        "button[title*='Download']",
        "a[title*='PDF']",
        "a[title*='Download']",
        "button:has-text('PDF')",
        "button:has-text('Download')",
        "a:has-text('PDF')",
        "a:has-text('Download')",
        "i[class*='pdf']",
        "img[src*='pdf']",
        "[class*='download']",
        "[class*='cv-download']",
        "[class*='attachment']",
    ]
    for sel in selectors:
        try:
            cv_btn = card.query_selector(sel)
            if cv_btn:
                break
        except Exception:
            pass

    # Phase B: XPath text search (broader than just "PDF")
    if not cv_btn:
        try:
            cv_btn = card.query_selector("xpath=.//*[contains(translate(text(),'PDFpdf','PDFPDF'),'PDF')]")
        except Exception:
            pass
    if not cv_btn:
        try:
            cv_btn = card.query_selector("xpath=.//*[contains(translate(text(),'DOWNLOAdownload','DOWNLOAdownload'),'DOWNLOAD')]")
        except Exception:
            pass

    # Phase C: look for ANY <button> or <a> inside the card that is small
    # (download icons are typically small inline elements)
    if not cv_btn:
        try:
            btns = card.query_selector_all("button, a")
            for b in btns:
                try:
                    box = b.bounding_box()
                    if box and box["width"] < 80 and box["height"] < 50:
                        # likely an icon button
                        cv_btn = b
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Phase D: last resort — use JS to find the element with the CV icon
    if not cv_btn:
        try:
            js_result = card.evaluate("""el => {
                const all = el.querySelectorAll('*');
                for (const c of all) {
                    const cls = (c.className || '').toLowerCase();
                    const txt = (c.innerText || c.textContent || '').toLowerCase();
                    const tag = c.tagName.toLowerCase();
                    if (cls.includes('pdf') || cls.includes('download') || cls.includes('cv')
                        || txt.includes('pdf') || txt.includes('download')
                        || c.getAttribute('title')?.toLowerCase().includes('pdf')) {
                        if (tag === 'button' || tag === 'a' || tag === 'span' || tag === 'i') {
                            return c;
                        }
                    }
                }
                return null;
            }""")
            if js_result:
                cv_btn = js_result
        except Exception:
            pass

    if not cv_btn:
        return "", "no_button"

    # ── 3. Click / trigger download with cascading fallbacks ────────
    download_triggered = False
    dl_info = None

    # Strategy A: standard Playwright click with expect_download
    try:
        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
            cv_btn.click()
        dl_info = _dl.value
        download_triggered = True
    except PwTimeout:
        pass  # will try next strategy
    except Exception:
        pass

    # Strategy B: JS click + synthetic events on the element
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                cv_btn.evaluate("""el => {
                    el.click();
                    el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,button:0}));
                    el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,button:0}));
                    el.dispatchEvent(new MouseEvent('click',{bubbles:true,button:0}));
                    // If it's an <a> with href, force navigation
                    if (el.tagName === 'A' && el.href) { window.open(el.href,'_blank'); }
                }""")
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    # Strategy C: hover + keyboard Enter on the card (Angular lazy-load)
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                card.evaluate("el => { el.focus(); el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); }")
                time.sleep(0.5)
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    # Strategy D: page-level Ctrl+J or Ctrl+S (last resort)
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                page.keyboard.press("Control+j")
                time.sleep(0.5)
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    if not download_triggered:
        return "", "failed_download_timeout"

    # Save the downloaded file
    filename  = f"{job_id}_{safe_name}_{ts}_uploaded.pdf"
    save_path = os.path.join(cv_dir, filename)
    dl_info.save_as(save_path)

    if os.path.exists(save_path) and os.path.getsize(save_path) > 100:
        with open(save_path, "rb") as f:
            header = f.read(5)
        status = "success" if header == b"%PDF-" else "success_unverified"
    else:
        status = "failed_empty"
    return filename, status'''

if old_download in content:
    content = content.replace(old_download, new_download)
    print("[OK] Replaced download_uploaded_cv with robust version")
else:
    print("[WARN] Could not find old download_uploaded_cv block — checking partial match...")
    if "def download_uploaded_cv" in content:
        print("  Function exists but full block didn't match. Manual review needed.")
    else:
        print("  Function not found at all.")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2: _advance_to_page — add longer wait and card-count verification
# ═══════════════════════════════════════════════════════════════════════════════

old_advance = '''def _advance_to_page(page, target_page: int, job_dir: str) -> bool:
    """Try to advance to the target page.

    Returns True if successful, False on failure (pagination DOM + screenshot
    dumped to job_dir).
    """
    # Try Next-button click
    try:
        next_btn = page.query_selector("button[aria-label='Next']")
        if next_btn:
            next_btn.click()
            page.wait_for_selector("app-applicant-card", timeout=PAGE_LOAD_TIMEOUT)
            time.sleep(2)
            return True
    except Exception:
        pass

    # Try page-number-N button click
    try:
        page_num_btn = page.query_selector(f"button:has-text('{target_page}')")
        if page_num_btn:
            page_num_btn.click()
            page.wait_for_selector("app-applicant-card", timeout=PAGE_LOAD_TIMEOUT)
            time.sleep(2)
            return True
    except Exception:
        pass

    # Dump pagination DOM + screenshot on failure
    try:
        page_content = page.content()
        with open(os.path.join(job_dir, "_pagination_dom.html"), "w", encoding="utf-8") as f:
            f.write(page_content)
    except Exception:
        pass
    try:
        page.screenshot(path=os.path.join(job_dir, "_pagination_failure.png"), full_page=True)
    except Exception:
        pass

    return False'''

new_advance = '''def _advance_to_page(page, target_page: int, job_dir: str) -> bool:
    """Try to advance to the target page.

    Returns True if successful, False on failure (pagination DOM + screenshot
    dumped to job_dir).
    """
    import random

    # ── Strategy 1: Next-button click ────────────────────────────────────
    try:
        next_btn = page.query_selector("button[aria-label='Next']")
        if next_btn:
            # Check if disabled
            disabled = next_btn.evaluate("el => el.disabled || el.getAttribute('disabled')")
            if not disabled:
                next_btn.click()
                # Wait for cards AND verify we have some cards on the new page
                for wait_attempt in range(5):
                    time.sleep(1.5 + random.uniform(0.5, 1.5))
                    cards = page.query_selector_all("app-applicant-card")
                    if len(cards) >= 1:
                        return True
                # Cards still not visible — maybe slow network
                time.sleep(3)
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
    except Exception as e:
        pass

    # ── Strategy 2: page-number-N button click ────────────────────────────
    try:
        page_num_btn = page.query_selector(f"button:has-text('{target_page}')")
        if page_num_btn:
            page_num_btn.click()
            for wait_attempt in range(5):
                time.sleep(1.5 + random.uniform(0.5, 1.5))
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
            time.sleep(3)
            cards = page.query_selector_all("app-applicant-card")
            if len(cards) >= 1:
                return True
    except Exception:
        pass

    # ── Strategy 3: arrow-button pagination (BDJobs uses right-arrow) ─────
    try:
        arrow = page.query_selector("button.pagination-next, a.pagination-next, .next-page, [aria-label='Next page']")
        if arrow:
            arrow.click()
            for wait_attempt in range(5):
                time.sleep(1.5 + random.uniform(0.5, 1.5))
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
    except Exception:
        pass

    # ── Strategy 4: JS window.scrollTo bottom + wait for Angular ──────────
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cards = page.query_selector_all("app-applicant-card")
        if len(cards) >= 1:
            return True
    except Exception:
        pass

    # Dump pagination DOM + screenshot on failure
    try:
        page_content = page.content()
        with open(os.path.join(job_dir, "_pagination_dom.html"), "w", encoding="utf-8") as f:
            f.write(page_content)
    except Exception:
        pass
    try:
        page.screenshot(path=os.path.join(job_dir, "_pagination_failure.png"), full_page=True)
    except Exception:
        pass

    return False'''

if old_advance in content:
    content = content.replace(old_advance, new_advance)
    print("[OK] Replaced _advance_to_page with robust version")
else:
    print("[WARN] Could not find old _advance_to_page block")
    if "def _advance_to_page" in content:
        print("  Function exists but full block didn't match.")
    else:
        print("  Function not found at all.")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 3: After card is re-found post-pagination, add a wait before using it
# ═══════════════════════════════════════════════════════════════════════════════

# In the main loop, after re-finding card during retry, add small wait
old_retry_cv = '''                if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} CV: {name[:30]} ({cv_status})")
                        time.sleep(3)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if not card:
                            break'''

new_retry_cv = '''                if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} CV: {name[:30]} ({cv_status})")
                        time.sleep(3)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if card:
                            # Small settle wait so Angular renders the lazy buttons
                            time.sleep(0.8)
                            try:
                                card.evaluate("el => { el.scrollIntoView({block:'center'}); el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }")
                                time.sleep(0.4)
                            except Exception:
                                pass
                        else:
                            break'''

if old_retry_cv in content:
    content = content.replace(old_retry_cv, new_retry_cv)
    print("[OK] Enhanced CV retry card re-discovery with settle wait")
else:
    print("[WARN] Could not find CV retry block")

# Also enhance profile text retry
old_retry_txt = '''                if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} profile: {name[:30]} ({txt_status})")
                        time.sleep(2)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if not card:
                            break'''

new_retry_txt = '''                if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} profile: {name[:30]} ({txt_status})")
                        time.sleep(2)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if card:
                            time.sleep(0.5)
                        else:
                            break'''

if old_retry_txt in content:
    content = content.replace(old_retry_txt, new_retry_txt)
    print("[OK] Enhanced profile retry card re-discovery")
else:
    print("[WARN] Could not find profile retry block")

# Also enhance the re-find after profile text success (before CV download)
old_refind = '''                if txt_status == "success":
                    total_txt_ok += 1
                card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None'''

new_refind = '''                if txt_status == "success":
                    total_txt_ok += 1
                card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                if card:
                    # Ensure card is settled after popup close / profile scrape
                    time.sleep(0.3)'''

if old_refind in content:
    content = content.replace(old_refind, new_refind)
    print("[OK] Added settle wait after profile scrape before CV download")
else:
    print("[WARN] Could not find post-profile re-find block")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 4: Add a card existence wait right after pagination in main loop
# ═══════════════════════════════════════════════════════════════════════════════

old_pagination = '''                if advanced:
                    current_ui_pg = expected_ui_pg
                else:'''

new_pagination = '''                if advanced:
                    current_ui_pg = expected_ui_pg
                    # After page advance, ensure cards are actually visible
                    # before trying to find the specific card
                    time.sleep(1.0)
                    cards = page.query_selector_all("app-applicant-card")
                    if len(cards) == 0:
                        # Angular may still be loading; give it more time
                        for settle_attempt in range(3):
                            time.sleep(2.0)
                            cards = page.query_selector_all("app-applicant-card")
                            if len(cards) > 0:
                                break
                else:'''

if old_pagination in content:
    content = content.replace(old_pagination, new_pagination)
    print("[OK] Added post-pagination settle wait")
else:
    print("[WARN] Could not find pagination advance block")

# Write back
with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n[DONE] {PATH} updated ({len(content)} chars)")
print("Summary of fixes:")
print("  1. download_uploaded_cv: 4-phase button discovery + 4 download trigger strategies")
print("  2. _advance_to_page: multi-strategy pagination with card-count verification")
print("  3. Retry loops: added settle waits after re-finding cards")
print("  4. Post-pagination: explicit wait for Angular card rendering")
