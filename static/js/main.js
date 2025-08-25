// Adrilly Sports Coaching Management - Main JavaScript File

// Modern Micro Animations System
class MicroAnimations {
    static init() {
        this.addIntersectionObserver();
        this.addScrollAnimations();
        this.addHoverEffects();
        this.addClickEffects();
    }
    
    static addIntersectionObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && 
                    !entry.target.dataset.staggerAnimated && 
                    entry.target.dataset.animating !== 'true') {
                    // Only animate if not already animated by staggered animations
                    this.safeAddAnimation(entry.target, 'animate-fade-in-up', 500);
                }
            });
        }, { threshold: 0.1 });
        
        // Observe all cards and content elements, but skip those that were stagger-animated
        setTimeout(() => {
            document.querySelectorAll('.content-card-modern, .table-row-modern, .user-card-mobile').forEach(el => {
                if (!el.dataset.staggerAnimated) {
                    observer.observe(el);
                }
            });
        }, 3000); // Wait for staggered animations to complete
    }
    
    static addScrollAnimations() {
        let ticking = false;
        
        function updateScrollProgress() {
            const scrolled = window.pageYOffset;
            const maxHeight = document.body.scrollHeight - window.innerHeight;
            const progress = (scrolled / maxHeight) * 100;
            
            // Update any progress indicators
            const progressBars = document.querySelectorAll('.scroll-progress');
            progressBars.forEach(bar => {
                bar.style.width = `${progress}%`;
            });
            
            ticking = false;
        }
        
        function requestTick() {
            if (!ticking) {
                requestAnimationFrame(updateScrollProgress);
                ticking = true;
            }
        }
        
        window.addEventListener('scroll', requestTick);
    }
    
    static addHoverEffects() {
        // Add hover effects to interactive elements
        document.addEventListener('mouseover', (e) => {
            if (e.target.matches('.btn, .action-item, .table-row-modern')) {
                e.target.style.transition = 'all 0.2s ease';
            }
        });
    }
    
    static addClickEffects() {
        // Add click ripple effects
        document.addEventListener('click', (e) => {
            if (e.target.matches('.btn, .action-item, .checkbox-modern')) {
                this.createRipple(e, e.target);
            }
        });
    }
    
    static createRipple(event, element) {
        const button = element || event.currentTarget || event.target;
        
        // Safety check to ensure we have a valid element
        if (!button || typeof button.getBoundingClientRect !== 'function') {
            return;
        }
        
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: scale(0);
            animation: ripple 0.6s ease-out;
            left: ${x}px;
            top: ${y}px;
            width: ${size}px;
            height: ${size}px;
            pointer-events: none;
        `;
        
        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 600);
    }
    
    static animateElement(element, animation = 'animate-bounce-in', duration = 600) {
        // Prevent conflicting animations
        if (element.dataset.animating === 'true') {
            return;
        }
        
        element.dataset.animating = 'true';
        element.classList.add(animation);
        
        setTimeout(() => {
            element.classList.remove(animation);
            element.dataset.animating = 'false';
        }, duration);
    }
    
    static safeAddAnimation(element, animationClass, duration = 500) {
        // Utility function to safely add animations without conflicts
        if (!element || element.dataset.animating === 'true') {
            return false;
        }
        
        element.dataset.animating = 'true';
        element.classList.add(animationClass);
        
        setTimeout(() => {
            element.classList.remove(animationClass);
            delete element.dataset.animating;
        }, duration);
        
        return true;
    }
    
    static showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} animate-slide-in-right`;
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
                <span class="toast-message">${message}</span>
            </div>
        `;
        
        // Add toast styles if not already present
        if (!document.querySelector('#toast-styles')) {
            const styles = document.createElement('style');
            styles.id = 'toast-styles';
            styles.textContent = `
                .toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: var(--bg-card);
                    color: var(--text-primary);
                    padding: 12px 16px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    z-index: 10000;
                    min-width: 300px;
                    border-left: 4px solid var(--accent-primary);
                }
                .toast.toast-success { border-left-color: var(--success, #10b981); }
                .toast.toast-error { border-left-color: var(--error, #ef4444); }
                .toast-content { display: flex; align-items: center; gap: 8px; }
                .toast-icon { font-size: 16px; }
                .toast-message { flex: 1; font-size: 14px; }
            `;
            document.head.appendChild(styles);
        }
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('animate-slide-out-right');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
}

// Initialize animations when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    MicroAnimations.init();
});

// Global utilities
window.Adrilly = {
    // Show alert message
    showAlert: function(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        const container = document.querySelector('.main-content');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.parentNode.removeChild(alertDiv);
                }
            }, 5000);
        }
    },

    // Show loading state
    showLoading: function(element) {
        if (element) {
            element.disabled = true;
            const originalText = element.textContent;
            element.setAttribute('data-original-text', originalText);
            element.innerHTML = '<span class="loading"></span> Loading...';
        }
    },

    // Hide loading state
    hideLoading: function(element) {
        if (element) {
            element.disabled = false;
            const originalText = element.getAttribute('data-original-text');
            if (originalText) {
                element.textContent = originalText;
                element.removeAttribute('data-original-text');
            }
        }
    },

    // Format date
    formatDate: function(date, format = 'YYYY-MM-DD') {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        
        switch (format) {
            case 'YYYY-MM-DD':
                return `${year}-${month}-${day}`;
            case 'YYYY-MM-DD HH:mm':
                return `${year}-${month}-${day} ${hours}:${minutes}`;
            case 'DD/MM/YYYY':
                return `${day}/${month}/${year}`;
            default:
                return `${year}-${month}-${day}`;
        }
    },

    // Validate phone number
    validatePhone: function(phone) {
        const phoneRegex = /^(\+|-)?[0-9]{10}$/;
        return phoneRegex.test(phone) && phone.length >= 10;
    },

    // API helper
    api: {
        request: async function(url, options = {}) {
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include'
            };
            
            const finalOptions = { ...defaultOptions, ...options };
            
            try {
                const response = await fetch(url, finalOptions);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.message || 'Request failed');
                }
                
                return data;
            } catch (error) {
                console.error('API Error:', error);
                throw error;
            }
        },

        get: function(url) {
            return this.request(url, { method: 'GET' });
        },

        post: function(url, data) {
            return this.request(url, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        put: function(url, data) {
            return this.request(url, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        delete: function(url) {
            return this.request(url, { method: 'DELETE' });
        }
    }
};

// Theme Management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    console.log(newTheme);
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update theme toggle button
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        themeToggle.textContent = newTheme === 'light' ? '☀️' : '🌙';
    }
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeToggle = document.querySelector('.theme-toggle');
    console.log(savedTheme);
    if (themeToggle) {
        themeToggle.textContent = savedTheme === 'light' ? '☀️' : '🌙';
    }
    const pageLoader = document.getElementById('pageLoader');
    const appContent = document.getElementById('appContent');
    
    // Simulate loading time (minimum 1.5 seconds for smooth effect)
    setTimeout(() => {
        // Fade out loader
        pageLoader.classList.add('fade-out');
        
        // Show app content
        appContent.classList.add('loaded');
        
        // Remove loader from DOM after animation
        setTimeout(() => {
            pageLoader.remove();
        }, 500);
        
        // Add staggered animations to elements
        addStaggeredAnimations();
    }, 500);
}

// Mobile sidebar toggle
document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    initializeTheme();
    // Mobile menu toggle
    const createMobileMenuButton = () => {
        if (window.innerWidth <= 768) {
            const header = document.querySelector('.header-content');
            if (header && !header.querySelector('.mobile-menu-btn')) {
                const menuBtn = document.createElement('button');
                menuBtn.className = 'mobile-menu-btn btn btn-outline btn-sm';
                menuBtn.innerHTML = '☰';
                menuBtn.onclick = toggleSidebar;
                header.insertBefore(menuBtn, header.firstChild);
            }
        }
    };

    const toggleSidebar = () => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('open');
        }
    };

    // Initialize mobile menu
    createMobileMenuButton();
    window.addEventListener('resize', createMobileMenuButton);

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768) {
            const sidebar = document.querySelector('.sidebar');
            const menuBtn = document.querySelector('.mobile-menu-btn');
            
            if (sidebar && sidebar.classList.contains('open') && 
                !sidebar.contains(e.target) && 
                !menuBtn?.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        }
    });

    // Form validation helpers
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const phoneInputs = form.querySelectorAll('input[type="tel"]');
            phoneInputs.forEach(input => {
                if (input.value && !Adrilly.validatePhone(input.value)) {
                    e.preventDefault();
                    input.classList.add('error');
                    Adrilly.showAlert('Please enter a valid phone number', 'error');
                    return false;
                }
            });
        });
    });

    // Auto-hide alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.opacity = '0';
                alert.style.transition = 'opacity 0.3s';
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 300);
            }
        }, 5000);
    });

    // Initialize tooltips (simple implementation)
    const elementsWithTooltips = document.querySelectorAll('[data-tooltip]');
    elementsWithTooltips.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.getAttribute('data-tooltip');
            tooltip.style.cssText = `
                position: absolute;
                background: #333;
                color: white;
                padding: 0.5rem;
                border-radius: 4px;
                font-size: 0.875rem;
                z-index: 1000;
                pointer-events: none;
                white-space: nowrap;
            `;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
            
            this._tooltip = tooltip;
        });
        
        element.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                document.body.removeChild(this._tooltip);
                this._tooltip = null;
            }
        });
    });
});

// Table utilities
window.TableUtils = {
    // Sort table
    sortTable: function(table, columnIndex, ascending = true) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const aText = a.cells[columnIndex].textContent.trim();
            const bText = b.cells[columnIndex].textContent.trim();
            
            // Check if numeric
            const aNum = parseFloat(aText);
            const bNum = parseFloat(bText);
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return ascending ? aNum - bNum : bNum - aNum;
            }
            
            // String comparison
            return ascending ? 
                aText.localeCompare(bText) : 
                bText.localeCompare(aText);
        });
        
        // Reorder rows
        rows.forEach(row => tbody.appendChild(row));
    },

    // Filter table
    filterTable: function(table, searchTerm) {
        const tbody = table.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const matches = text.includes(searchTerm.toLowerCase());
            row.style.display = matches ? '' : 'none';
        });
    }
};

// Form utilities
window.FormUtils = {
    // Serialize form to object
    serialize: function(form) {
        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            if (data[key]) {
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        return data;
    },

    // Validate form
    validate: function(form) {
        const errors = [];
        const requiredFields = form.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                errors.push(`${field.name || field.id} is required`);
                field.classList.add('error');
            } else {
                field.classList.remove('error');
            }
        });
        
        // Phone validation
        const phoneFields = form.querySelectorAll('input[type="tel"]');
        phoneFields.forEach(field => {
            if (field.value && !Adrilly.validatePhone(field.value)) {
                errors.push('Please enter a valid phone number');
                field.classList.add('error');
            }
        });
        
        // Email validation
        const emailFields = form.querySelectorAll('input[type="email"]');
        emailFields.forEach(field => {
            if (field.value && !field.value.includes('@')) {
                errors.push('Please enter a valid email address');
                field.classList.add('error');
            }
        });
        
        return errors;
    }
};

// Date utilities
window.DateUtils = {
    // Get today's date in YYYY-MM-DD format
    today: function() {
        return new Date().toISOString().split('T')[0];
    },

    // Add days to date
    addDays: function(date, days) {
        const result = new Date(date);
        result.setDate(result.getDate() + days);
        return result;
    },

    // Format date for display
    formatForDisplay: function(date) {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },

    // Get time from datetime
    getTime: function(datetime) {
        return new Date(datetime).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Adrilly, TableUtils, FormUtils, DateUtils };
} 