/**
 * OEM Configuration Loader
 * Dynamically loads and applies OEM configuration
 */

async function loadOEMConfig() {
    try {
        const response = await fetch('/api/oem-config');
        if (!response.ok) {
            console.warn('Failed to load OEM config:', response.status);
            return {
                branding: {},
                assets: {},
                advanced: {}
            };
        }
        
        const oemConfig = await response.json();
        console.log('OEM Config loaded:', oemConfig);
        
        applyOEMConfig(oemConfig);
        return oemConfig;
    } catch (error) {
        console.warn('Error loading OEM config:', error);
        return {
            branding: {},
            assets: {},
            advanced: {}
        };
    }
}

/**
 * Convert relative image paths to absolute paths for static files
 */
function getImagePath(imagePath) {
    if (!imagePath) return null;
    
    // If it's not an image path (no extension), return as-is (emoji)
    if (!imagePath.includes('/') && !imagePath.includes('.')) {
        return imagePath;
    }
    
    // If it already has a leading slash, return as-is
    if (imagePath.startsWith('/')) {
        return imagePath;
    }
    
    // Add /static/ prefix for relative paths
    return '/static/' + imagePath;
}

function applyOEMConfig(oemConfig) {
    const branding = oemConfig.branding || {};
    const assets = oemConfig.assets || {};
    const advanced = oemConfig.advanced || {};
    
    // Apply brand icon (header)
    const brandIcon = assets.brand_icon || '🎙️';
    const iconScale = advanced.icon_scale || 1.0;
    const baseHeaderHeight = 40;  // Base height for header icon
    const maxHeaderHeight = Math.round(baseHeaderHeight * iconScale);
    
    const brandElements = document.querySelectorAll('.brand span:first-child');
    brandElements.forEach(el => {
        if (!el.querySelector('img')) {
            if (brandIcon.includes('/') || brandIcon.includes('.')) {
                const img = document.createElement('img');
                img.src = getImagePath(brandIcon);
                img.alt = 'Brand Icon';
                img.style.maxHeight = maxHeaderHeight + 'px';
                img.style.width = 'auto';
                img.style.maxWidth = '100%';
                img.style.display = 'block';
                el.innerHTML = '';
                el.appendChild(img);
            } else {
                el.textContent = brandIcon;
            }
        }
    });
    
    // Apply favicon - must apply to all pages
    if (assets.favicon) {
        // Remove ALL old favicon links
        const oldLinks = document.querySelectorAll("link[rel='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']");
        oldLinks.forEach(link => link.remove());
        
        const faviconPath = getImagePath(assets.favicon);
        
        // Create primary favicon link
        const link = document.createElement('link');
        link.rel = 'icon';
        link.href = faviconPath + '?t=' + Date.now();  // Add timestamp to bust cache
        
        // Set correct type based on file extension
        if (faviconPath.endsWith('.ico')) {
            link.type = 'image/x-icon';
        } else if (faviconPath.endsWith('.png')) {
            link.type = 'image/png';
        } else if (faviconPath.endsWith('.jpg') || faviconPath.endsWith('.jpeg')) {
            link.type = 'image/jpeg';
        } else if (faviconPath.endsWith('.svg')) {
            link.type = 'image/svg+xml';
        }
        
        document.head.appendChild(link);
        
        // Also create shortcut icon link for better compatibility
        const shortcutLink = document.createElement('link');
        shortcutLink.rel = 'shortcut icon';
        shortcutLink.href = faviconPath + '?t=' + Date.now();
        document.head.appendChild(shortcutLink);
        
        console.log('✓ Favicon applied:', faviconPath);
        console.log('✓ Cache buster timestamp:', Date.now());
    } else {
        console.warn('No favicon configured in OEM assets');
    }
    
    // Apply brand titles
    const brandTitleElements = document.querySelectorAll('.brand span:last-child, [data-i18n="brand"], [data-i18n="brand_admin"]');
    if (window.currentPage === 'admin') {
        const adminTitle = branding.admin_title || 'EzySpeech Admin';
        brandTitleElements.forEach(el => {
            if (!el.querySelector('img')) {
                el.textContent = adminTitle;
            }
        });
        
        // Update page title
        if (branding.admin_title) {
            document.title = branding.admin_title;
        }
    } else if (window.currentPage === 'user') {
        const userTitle = branding.user_title || 'EzySpeech User';
        brandTitleElements.forEach(el => {
            if (!el.querySelector('img')) {
                el.textContent = userTitle;
            }
        });
        
        // Update page title
        if (branding.user_title) {
            document.title = branding.user_title;
        }
    } else if (window.currentPage === 'login') {
        const loginTitle = branding.login_title || 'EzySpeech Admin';
        const h1 = document.querySelector('.login-logo h1');
        if (h1 && branding.login_title) {
            h1.textContent = loginTitle;
        }
        
        // Apply login icon
        const loginIcon = assets.login_icon || '🎙️';
        const baseLoginHeight = 60;  // Base height for login icon
        const maxLoginHeight = Math.round(baseLoginHeight * iconScale);
        const loginIconEl = document.querySelector('.login-logo-icon');
        if (loginIconEl) {
            if (loginIcon.includes('/') || loginIcon.includes('.')) {
                const img = document.createElement('img');
                img.src = getImagePath(loginIcon);
                img.alt = 'Brand Icon';
                img.style.maxHeight = maxLoginHeight + 'px';
                img.style.width = 'auto';
                img.style.maxWidth = '100%';
                img.style.display = 'block';
                loginIconEl.innerHTML = '';
                loginIconEl.appendChild(img);
            } else {
                loginIconEl.textContent = loginIcon;
            }
        }
        
        // Update page title
        if (branding.login_title) {
            document.title = branding.login_title + ' - Login';
        }
    }
    
    // Store in window for access from other scripts
    window.OEM_CONFIG = oemConfig;
}

// Detect current page
function detectCurrentPage() {
    const path = window.location.pathname;
    // Check login page first (both /admin/login and /login)
    if (path.includes('/login')) {
        window.currentPage = 'login';
    } else if (path.includes('/admin')) {
        window.currentPage = 'admin';
    } else if (path === '/' || path === '') {
        window.currentPage = 'user';
    } else {
        window.currentPage = 'user';  // Default to user page
    }
}

// Auto-load on page load
document.addEventListener('DOMContentLoaded', () => {
    detectCurrentPage();
    loadOEMConfig();
});

// Also load immediately if document is already ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadOEMConfig);
} else {
    detectCurrentPage();
    loadOEMConfig();
}
