// Feature Cards Data
const features = [
    {
        title: "Effortless Class Management",
        description: "Schedule, cancel, and send reminders in seconds.",
        icon: "📅" // Placeholder for actual icon
    },
    {
        title: "QR-Based Attendance",
        description: "Smart attendance tracking with real-time validation.",
        icon: "📱" // Placeholder for actual icon
    },
    {
        title: "Coach & Announcement Tools",
        description: "Manage leaves, post updates, and keep everyone informed.",
        icon: "📢" // Placeholder for actual icon
    },
    {
        title: "Discover Experiences",
        description: "Students explore new centers and book one-time sessions.",
        icon: "🔍" // Placeholder for actual icon
    }
];

// Generate Feature Cards
function generateFeatureCards() {
    const featureSection = document.querySelector('#features .grid');
    features.forEach((feature, index) => {
        const card = document.createElement('div');
        card.className = 'feature-card opacity-0';
        card.innerHTML = `
            <div class="h-40 mb-6 flex items-center justify-center text-6xl">
                ${feature.icon}
            </div>
            <h3 class="text-xl font-bold mb-4">${feature.title}</h3>
            <p class="text-gray-300">${feature.description}</p>
        `;
        featureSection.appendChild(card);
        
        // Animate cards on scroll
        setTimeout(() => {
            card.classList.add('animate-scale-in');
        }, index * 200);
    });
}

// Intersection Observer for scroll animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-fade-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Initialize animations
function initAnimations() {
    // Observe elements with animation classes
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

// Mobile menu toggle
function initMobileMenu() {
    const menuButton = document.querySelector('nav button');
    const mobileMenu = document.createElement('div');
    mobileMenu.className = 'mobile-menu fixed inset-0 bg-bg-overlay backdrop-blur-sm hidden md:hidden';
    mobileMenu.innerHTML = `
        <div class="bg-bg-primary h-screen w-3/4 max-w-sm p-6 transform transition-transform">
            <div class="flex flex-col space-y-6">
                <a href="#features" class="text-lg hover:text-primary">Features</a>
                <a href="#why" class="text-lg hover:text-primary">Why botle</a>
                <a href="#showcase" class="text-lg hover:text-primary">Showcase</a>
                <a href="#testimonials" class="text-lg hover:text-primary">Testimonials</a>
                <hr class="border-bg-tertiary">
                <button class="w-full py-2 text-center hover:bg-bg-hover rounded-lg">Login</button>
                <button class="w-full py-2 text-center bg-primary text-bg-secondary rounded-lg hover:bg-primary-dark">Sign Up</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(mobileMenu);
    
    menuButton.addEventListener('click', () => {
        mobileMenu.classList.toggle('hidden');
    });
    
    mobileMenu.addEventListener('click', (e) => {
        if (e.target === mobileMenu) {
            mobileMenu.classList.add('hidden');
        }
    });
}

// Smooth scroll for navigation links
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
                // Close mobile menu if open
                document.querySelector('.mobile-menu')?.classList.add('hidden');
            }
        });
    });
}

// Showcase Data
const showcaseItems = [
    {
        title: "Admin Dashboard",
        description: "Comprehensive view of your coaching center",
        image: "dashboard-placeholder.jpg"
    },
    {
        title: "Attendance QR Scan",
        description: "Quick and reliable attendance tracking",
        image: "qr-placeholder.jpg"
    },
    {
        title: "Student Booking",
        description: "Seamless class booking experience",
        image: "booking-placeholder.jpg"
    }
];

// Testimonials Data
const testimonials = [
    {
        name: "Sarah Johnson",
        role: "Center Admin",
        quote: "botle made scheduling effortless and boosted our center's revenue.",
        image: "profile-placeholder.jpg"
    },
    {
        name: "Mike Chen",
        role: "Student",
        quote: "I love being able to try different classes before committing.",
        image: "profile-placeholder.jpg"
    },
    {
        name: "Priya Patel",
        role: "Coach",
        quote: "The attendance system saves me so much time every day.",
        image: "profile-placeholder.jpg"
    },
    {
        name: "David Kim",
        role: "Center Owner",
        quote: "Our student engagement has increased significantly since using botle.",
        image: "profile-placeholder.jpg"
    }
];

// Generate Showcase Items
function generateShowcaseItems() {
    const showcaseContainer = document.querySelector('.showcase-slides');
    showcaseItems.forEach((item, index) => {
        const slide = document.createElement('div');
        slide.className = 'showcase-item min-w-[300px] md:min-w-[400px] bg-bg-card rounded-xl p-6 opacity-0';
        slide.innerHTML = `
            <div class="h-[200px] mb-6 bg-bg-tertiary rounded-lg flex items-center justify-center">
                <span class="text-gray-500">Screenshot Placeholder</span>
            </div>
            <h3 class="text-xl font-bold mb-2">${item.title}</h3>
            <p class="text-gray-300">${item.description}</p>
        `;
        showcaseContainer.appendChild(slide);
        
        setTimeout(() => {
            slide.classList.add('animate-slide-in');
        }, index * 200);
    });
}

// Generate Testimonial Cards
function generateTestimonials() {
    const testimonialContainer = document.querySelector('.testimonials-container .flex');
    testimonials.forEach((testimonial, index) => {
        const card = document.createElement('div');
        card.className = 'testimonial-card opacity-0';
        card.innerHTML = `
            <div class="flex items-center space-x-4 mb-6">
                <div class="w-12 h-12 rounded-full bg-bg-tertiary flex items-center justify-center">
                    <span class="text-2xl">👤</span>
                </div>
                <div>
                    <h4 class="font-bold">${testimonial.name}</h4>
                    <p class="text-gray-400">${testimonial.role}</p>
                </div>
            </div>
            <p class="text-gray-300">"${testimonial.quote}"</p>
        `;
        testimonialContainer.appendChild(card);
        
        setTimeout(() => {
            card.classList.add('animate-fade-in');
        }, index * 200);
    });
}

// Generate Stats Bars
function generateStats() {
    const statsContainer = document.querySelector('.stats-container');
    const stats = [
        { label: 'No-shows Reduction', value: 30, color: 'primary' },
        { label: 'Slot Utilization', value: 20, color: 'secondary' }
    ];
    
    stats.forEach((stat, index) => {
        const bar = document.createElement('div');
        bar.className = `stat-bar relative h-20 mb-4 bg-bg-tertiary rounded-lg overflow-hidden opacity-0`;
        bar.innerHTML = `
            <div class="absolute inset-y-0 left-0 bg-${stat.color} transition-all duration-1000" style="width: 0%"></div>
            <div class="relative z-10 h-full flex items-center justify-between px-4">
                <span>${stat.label}</span>
                <span class="font-bold">${stat.value}%</span>
            </div>
        `;
        statsContainer.appendChild(bar);
        
        setTimeout(() => {
            bar.classList.add('animate-fade-in');
            bar.querySelector('.bg-${stat.color}').style.width = `${stat.value}%`;
        }, index * 200);
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    generateFeatureCards();
    generateShowcaseItems();
    generateTestimonials();
    generateStats();
    initAnimations();
    initMobileMenu();
    initSmoothScroll();
});
