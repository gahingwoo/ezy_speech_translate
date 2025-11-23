let SERVER_URL = '';

// XSS Protection
function sanitizeInput(input) {
    if (typeof input !== 'string') return '';
    return input
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;')
        .trim();
}

function toggleLoginTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    document.getElementById('loginThemeIcon').textContent = newTheme === 'dark' ? '☀️' : '🌙';
    document.getElementById('loginThemeText').textContent = newTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
}

async function login(event) {
    if (event) event.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('loginError');
    const loginButton = document.getElementById('loginButton');

    // Validate inputs
    if (!username || !password) {
        errorEl.textContent = 'Please fill in all fields';
        errorEl.style.display = 'block';
        return false;
    }

    // Sanitize username
    const sanitizedUsername = sanitizeInput(username);

    // Basic validation
    if (sanitizedUsername.length > 50) {
        errorEl.textContent = 'Username too long';
        errorEl.style.display = 'block';
        return false;
    }

    if (password.length > 100) {
        errorEl.textContent = 'Password too long';
        errorEl.style.display = 'block';
        return false;
    }

    // Disable button during login
    loginButton.disabled = true;
    loginButton.textContent = 'Signing in...';

    try {
        const response = await fetch(`${SERVER_URL}/api/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: sanitizedUsername,
                password: password
            })
        });

        const data = await response.json();

        if (data.success && data.token) {
            // Store token
            localStorage.setItem('authToken', data.token);

            // Redirect to admin page
            window.location.href = '/admin';
        } else {
            errorEl.textContent = 'Invalid credentials';
            errorEl.style.display = 'block';
            loginButton.disabled = false;
            loginButton.textContent = 'Sign In';
        }
    } catch (error) {
        errorEl.textContent = 'Connection failed. Is the server running?';
        errorEl.style.display = 'block';
        loginButton.disabled = false;
        loginButton.textContent = 'Sign In';
        console.error('Login error:', error);
    }

    return false;
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Apply saved theme
    const storedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', storedTheme);

    if (storedTheme === 'dark') {
        document.getElementById('loginThemeIcon').textContent = '☀️';
        document.getElementById('loginThemeText').textContent = 'Light Mode';
    }

    // Load server config
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        SERVER_URL = `${window.location.protocol}//${window.location.hostname}:${config.mainServerPort}`;
        console.log('Main server URL:', SERVER_URL);
    } catch (error) {
        console.error('Failed to load config:', error);
        SERVER_URL = `${window.location.protocol}//${window.location.hostname}:1915`;
    }

    // Check if already logged in
    const savedToken = localStorage.getItem('authToken');
    if (savedToken) {
        // Verify token is still valid by trying to access admin page
        window.location.href = '/admin';
    }

    // Setup form submit
    document.getElementById('loginForm').addEventListener('submit', login);
    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login(e);
    });
});

console.log('✅ Login page ready');