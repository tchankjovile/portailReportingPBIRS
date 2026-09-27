/* =====================================================
   BICEC PBIRS Portal — Alpine.js Helpers & Global JS
   ===================================================== */

/* ── Toast Notification System ── */
function showToast(message, type = 'default', duration = 3000) {
    const existing = document.getElementById('bicec-toast');
    if (existing) existing.remove();

    const icons = {
        success:  `<svg class="w-5 h-5 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`,
        favorite: `<svg class="w-5 h-5 text-orange-300 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`,
        error:    `<svg class="w-5 h-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`,
        default:  `<svg class="w-5 h-5 text-bicec-orange shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    };

    const bgMap = {
        success:  'from-emerald-800 to-emerald-700',
        favorite: 'from-bicec-chocolate to-bicec-orange',
        error:    'from-red-800 to-red-700',
        default:  'from-gray-900 to-gray-800',
    };

    const toast = document.createElement('div');
    toast.id = 'bicec-toast';
    toast.className = `fixed bottom-6 right-6 z-[9999] flex items-center gap-3 px-4 py-3.5 rounded-2xl bg-gradient-to-r ${bgMap[type] || bgMap.default} text-white text-sm font-medium shadow-2xl min-w-[260px] max-w-sm`;
    toast.style.animation = 'slideInToast 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards';
    toast.innerHTML = `${icons[type] || icons.default}<span>${message}</span>`;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'fadeOutToast 0.3s ease forwards';
        setTimeout(() => toast.remove(), 350);
    }, duration);
}

/* ── HTMX Global Event Listeners ── */
document.addEventListener('DOMContentLoaded', () => {

    // Animate page content on load
    const main = document.querySelector('main');
    if (main) {
        main.style.opacity = '0';
        main.style.transform = 'translateY(10px)';
        requestAnimationFrame(() => {
            main.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
            main.style.opacity = '1';
            main.style.transform = 'translateY(0)';
        });
    }

    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+K / Cmd+K → focus search bar
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('input[name="q"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        // Escape → exit full-screen embed if active
        if (e.key === 'Escape') {
            const fullscreenEl = document.querySelector('.fullscreen-mode');
            if (fullscreenEl) {
                fullscreenEl.classList.remove('fullscreen-mode');
                showToast('Mode plein écran désactivé', 'default', 2000);
            }
        }
    });
});

/* ── HTMX After-Settle Hook (toast after favorite toggle) ── */
document.addEventListener('htmx:afterSettle', (event) => {
    const target = event.target;

    // If a favorite button was swapped
    if (target && target.matches('[hx-post*="/api/favorites/toggle/"]')) {
        const isFav = target.querySelector('svg')?.classList?.contains('fill-\\[\\#E67900\\]');
        if (isFav) {
            showToast('Rapport ajouté aux favoris !', 'favorite', 2500);
        } else {
            showToast('Rapport retiré des favoris', 'default', 2000);
        }
    }
});

/* ── Full-Screen Report Viewer ── */
function toggleFullScreen(containerId = 'report-embed-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!container.classList.contains('fullscreen-mode')) {
        container.classList.add('fullscreen-mode');
        document.body.style.overflow = 'hidden';
        showToast('Mode plein écran activé — Appuyez sur Échap pour quitter', 'success', 3000);
    } else {
        container.classList.remove('fullscreen-mode');
        document.body.style.overflow = '';
        showToast('Mode plein écran désactivé', 'default', 2000);
    }
}

/* ── Alpine.js Global Store / Data Factories ── */
document.addEventListener('alpine:init', () => {

    // Global app store
    Alpine.store('app', {
        sidebarOpen: window.innerWidth >= 1024,
        darkMode: localStorage.getItem('bicec_dark_mode') === 'true',

        init() {
            // Watch dark mode toggle and persist to localStorage
            this.$watch('darkMode', (val) => {
                localStorage.setItem('bicec_dark_mode', val);
                document.documentElement.classList.toggle('dark', val);
            });
            // Apply persisted dark mode on init
            if (this.darkMode) {
                document.documentElement.classList.add('dark');
            }
        },

        toggleSidebar() { this.sidebarOpen = !this.sidebarOpen; },
        toggleDarkMode() { this.darkMode = !this.darkMode; }
    });
});

/* ── Copy to Clipboard Utility ── */
function copyToClipboard(text, successMsg = 'Copié dans le presse-papiers !') {
    navigator.clipboard.writeText(text).then(() => {
        showToast(successMsg, 'success', 2500);
    }).catch(() => {
        // Fallback for older browsers
        const el = document.createElement('textarea');
        el.value = text;
        el.style.position = 'fixed';
        el.style.opacity = '0';
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        showToast(successMsg, 'success', 2500);
    });
}

/* ── Report iFrame Load Handler ── */
function onReportIframeLoad(iframe) {
    const spinner = document.getElementById('iframe-spinner');
    if (spinner) {
        spinner.style.transition = 'opacity 0.3s ease';
        spinner.style.opacity = '0';
        setTimeout(() => { if (spinner) spinner.remove(); }, 350);
    }
    if (iframe) {
        iframe.style.opacity = '0';
        iframe.style.transition = 'opacity 0.4s ease';
        requestAnimationFrame(() => { iframe.style.opacity = '1'; });
    }
}

/* ── Export / Print Report Action ── */
function exportReport(reportId, format = 'PDF') {
    showToast(`Export ${format} du rapport en cours...`, 'default', 3000);
    // Open PBIRS native export endpoint
    window.open(`/reports/${reportId}/export?format=${format}`, '_blank');
}
