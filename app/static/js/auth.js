import { auth, provider, signInWithPopup, signOut } from './firebase-config.js';

// Google Sign-In Handler
export async function signInWithGoogle() {
    try {
        const result = await signInWithPopup(auth, provider);
        const user = result.user;

        // Get ID token
        const idToken = await user.getIdToken();

        // Detect if running under /join subdirectory
        const isSubdir = window.location.pathname.startsWith('/join');
        const basePath = isSubdir ? '/join' : '';

        // Send token to backend for verification
        const response = await fetch(basePath + '/auth/google-login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                idToken: idToken,
                email: user.email,
                displayName: user.displayName,
                photoURL: user.photoURL
            })
        });

        const data = await response.json();

        if (data.success) {
            // Redirect based on user type
            window.location.href = data.redirect_url;
        } else {
            showMessage(data.message || 'Authentication failed', 'error');
        }
    } catch (error) {
        console.error('Error during sign-in:', error);
        showMessage('Sign-in failed: ' + error.message, 'error');
    }
}

// Sign Out Handler
export async function handleSignOut() {
    try {
        await signOut(auth);

        // Detect if running under /join subdirectory
        const isSubdir = window.location.pathname.startsWith('/join');
        const basePath = isSubdir ? '/join' : '';

        // Call backend logout
        const response = await fetch(basePath + '/auth/logout', {
            method: 'POST'
        });

        window.location.href = basePath + '/';
    } catch (error) {
        console.error('Error during sign-out:', error);
        showMessage('Sign-out failed', 'error');
    }
}

// Display message helper
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    messageDiv.style.position = 'fixed';
    messageDiv.style.top = '100px';
    messageDiv.style.right = '20px';
    messageDiv.style.zIndex = '9999';

    document.body.appendChild(messageDiv);

    setTimeout(() => {
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateX(20px)';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}

// Listen for auth state changes
auth.onAuthStateChanged((user) => {
    console.log('Auth state changed:', user ? user.email : 'No user');
});
