/**
 * TigerGraph Agentic Fraud Console — Client Interactivity
 */

// Navigate to selected case from dropdown
function navigateToCase(caseId) {
    if (caseId) {
        window.location.href = '/case/' + encodeURIComponent(caseId);
    }
}

// Copy Raw JSON to clipboard
function copyRawJson() {
    const jsonBlock = document.getElementById('raw-json-block');
    if (!jsonBlock) return;
    
    const text = jsonBlock.innerText;
    navigator.clipboard.writeText(text).then(() => {
        const copyBtn = document.querySelector('.btn-copy');
        if (copyBtn) {
            const originalText = copyBtn.innerText;
            copyBtn.innerText = 'Copied! ✓';
            setTimeout(() => {
                copyBtn.innerText = originalText;
            }, 1800);
        }
    }).catch(err => {
        console.error('Failed to copy JSON:', err);
    });
}

// Keyboard shortcuts for fast presentation navigation: ArrowLeft (prev), ArrowRight (next)
document.addEventListener('keydown', function(event) {
    // Ignore if focus is in an input or select
    if (['input', 'textarea', 'select'].includes(document.activeElement.tagName.toLowerCase())) {
        return;
    }

    if (event.key === 'ArrowLeft') {
        const prevBtn = document.getElementById('btn-prev');
        if (prevBtn && prevBtn.tagName.toLowerCase() === 'a' && prevBtn.href) {
            window.location.href = prevBtn.href;
        }
    } else if (event.key === 'ArrowRight') {
        const nextBtn = document.getElementById('btn-next');
        if (nextBtn && nextBtn.tagName.toLowerCase() === 'a' && nextBtn.href) {
            window.location.href = nextBtn.href;
        }
    }
});
