// Login Page JavaScript
class LoginManager {
    constructor() {
        this.initElements();
        this.attachEventListeners();
        this.checkRememberedUser();
    }

    initElements() {
        this.elements = {
            loginForm: document.getElementById('loginForm'),
            username: document.getElementById('username'),
            password: document.getElementById('password'),
            rememberMe: document.getElementById('rememberMe'),
            signupLink: document.getElementById('signupLink'),
            forgotPassword: document.querySelector('.forgot-password')
        };
    }

    attachEventListeners() {
        this.elements.loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        this.elements.signupLink.addEventListener('click', (e) => this.showSignup(e));
        this.elements.forgotPassword.addEventListener('click', (e) => this.showForgotPassword(e));
    }

    handleLogin(e) {
        e.preventDefault();

        const username = this.elements.username.value.trim();
        const password = this.elements.password.value.trim();

        // Basic validation
        if (!username || !password) {
            this.showError('Please fill in all fields');
            return;
        }

        // For demo purposes, accept any username/password
        // In a real app, this would validate against a server
        this.showSuccess('Login successful! Redirecting...');

        // Set login status
        localStorage.setItem('isLoggedIn', 'true');

        // Remember user if checkbox is checked
        if (this.elements.rememberMe.checked) {
            this.rememberUser(username);
        }

        // Redirect to game after a short delay
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1500);
    }

    showSignup(e) {
        e.preventDefault();
        this.showError('Sign up feature coming soon! For now, use any username and password to login.');
    }

    showForgotPassword(e) {
        e.preventDefault();
        this.showError('Password reset feature coming soon! For demo, use any password.');
    }

    showError(message) {
        this.hideMessages();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        this.elements.loginForm.insertBefore(errorDiv, this.elements.loginForm.firstChild);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    showSuccess(message) {
        this.hideMessages();
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.textContent = message;
        this.elements.loginForm.insertBefore(successDiv, this.elements.loginForm.firstChild);
    }

    hideMessages() {
        const messages = document.querySelectorAll('.error-message, .success-message');
        messages.forEach(msg => msg.remove());
    }

    rememberUser(username) {
        localStorage.setItem('rememberedUser', username);
    }

    checkRememberedUser() {
        const rememberedUser = localStorage.getItem('rememberedUser');
        if (rememberedUser) {
            this.elements.username.value = rememberedUser;
            this.elements.rememberMe.checked = true;
        }
    }
}

// Add some visual enhancements
class LoginAnimations {
    constructor() {
        this.initAnimations();
    }

    initAnimations() {
        // Add subtle animation to the login card
        const loginCard = document.querySelector('.login-card');
        if (loginCard) {
            loginCard.style.animation = 'slideIn 0.5s ease-out';
        }

        // Add focus animations to inputs
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('focus', () => {
                input.parentElement.style.transform = 'scale(1.02)';
            });

            input.addEventListener('blur', () => {
                input.parentElement.style.transform = 'scale(1)';
            });
        });
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .form-group {
        transition: transform 0.2s ease;
    }
`;
document.head.appendChild(style);

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Check if user is already logged in
    if (localStorage.getItem('isLoggedIn')) {
        window.location.href = 'index.html';
        return;
    }
    
    const loginManager = new LoginManager();
    const animations = new LoginAnimations();
});
