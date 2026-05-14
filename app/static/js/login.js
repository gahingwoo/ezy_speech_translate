let SERVER_URL = '';

// Pure-JS SHA-256 — works in all contexts (HTTP, IP access, CF Tunnel, no SubtleCrypto needed)
function sha256hex(str) {
    function rr(n, x) { return (x >>> n) | (x << (32 - n)); }
    const K = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ];
    let H = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const bytes = new TextEncoder().encode(str);
    const len = bytes.length;
    const blocks = Math.ceil((len + 9) / 64);
    const padded = new Uint8Array(blocks * 64);
    padded.set(bytes);
    padded[len] = 0x80;
    const dv = new DataView(padded.buffer);
    dv.setUint32(padded.length - 4, (len * 8) & 0xffffffff, false);
    for (let i = 0; i < blocks; i++) {
        const W = new Array(64);
        for (let j = 0; j < 16; j++) W[j] = dv.getUint32(i * 64 + j * 4, false);
        for (let j = 16; j < 64; j++) {
            const s0 = rr(7,W[j-15]) ^ rr(18,W[j-15]) ^ (W[j-15]>>>3);
            const s1 = rr(17,W[j-2])  ^ rr(19,W[j-2])  ^ (W[j-2]>>>10);
            W[j] = (W[j-16] + s0 + W[j-7] + s1) >>> 0;
        }
        let [a,b,c,d,e,f,g,h] = H;
        for (let j = 0; j < 64; j++) {
            const S1   = rr(6,e)^rr(11,e)^rr(25,e);
            const ch   = (e&f)^(~e&g);
            const t1   = (h+S1+ch+K[j]+W[j]) >>> 0;
            const S0   = rr(2,a)^rr(13,a)^rr(22,a);
            const maj  = (a&b)^(a&c)^(b&c);
            const t2   = (S0+maj) >>> 0;
            h=g; g=f; f=e; e=(d+t1)>>>0; d=c; c=b; b=a; a=(t1+t2)>>>0;
        }
        H = H.map((v,idx)=>([a,b,c,d,e,f,g,h][idx]+v)>>>0);
    }
    return H.map(v => v.toString(16).padStart(8,'0')).join('');
}

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

    // Hash password on the client so plaintext never leaves the browser
    const passwordHash = sha256hex(password);

    try {
        // Always call admin server's login endpoint (same server as login page)
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            credentials: 'include',  // Include cookies for cross-origin requests
            body: JSON.stringify({
                username: sanitizedUsername,
                password_hash: passwordHash   // SHA-256 hash only — never send plaintext
            })
        });

        console.log('Login response status:', response.status);

        let data;
        try {
            data = await response.json();
            // NOTE: do not log `data` here — it contains the JWT token
        } catch (e) {
            console.error('Failed to parse response JSON:', e);
            errorEl.textContent = 'Invalid server response';
            errorEl.style.display = 'block';
            loginButton.disabled = false;
            loginButton.textContent = 'Sign In';
            return false;
        }

        console.log('Checking conditions:', {
            ok: response.ok,
            success: data.success,
            hasToken: !!data.token
        });

        if (response.ok && data.success && data.token) {
            console.log('Login successful, storing token');
            // Store token
            localStorage.setItem('authToken', data.token);

            // Redirect to admin page
            window.location.href = '/admin';
        } else {
            console.error('Login check failed:', data);
            errorEl.textContent = data.error || 'Invalid credentials';
            errorEl.style.display = 'block';
            loginButton.disabled = false;
            loginButton.textContent = 'Sign In';
        }
    } catch (error) {
        console.error('Login error caught:', error);
        console.error('Error type:', error.constructor.name);
        console.error('Error message:', error.message);
        errorEl.textContent = 'Connection failed. Is the server running?';
        errorEl.style.display = 'block';
        loginButton.disabled = false;
        loginButton.textContent = 'Sign In';
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

        // Prefer external URL if configured (for CF Tunnel or reverse proxy)
        if (config.mainServerUrl) {
            SERVER_URL = config.mainServerUrl;
        } else {
            // Fallback to building URL from protocol and port
            const protocol = config.mainServerProtocol || window.location.protocol.replace(':', '');
            SERVER_URL = `${protocol}://${window.location.hostname}:${config.mainServerPort}`;
        }

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