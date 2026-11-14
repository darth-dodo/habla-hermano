// Theme config moved from the inline Tailwind Play CDN config in base.html.
/** @type {import('tailwindcss').Config} */
export default {
    content: [
        './src/templates/**/*.html',
        './src/static/js/**/*.js',
        // Some routes return small HTML fragments built in Python.
        './src/**/*.py',
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                // Theme-aware colors using CSS variables
                surface: {
                    DEFAULT: 'var(--surface)',
                    elevated: 'var(--surface-elevated)',
                    overlay: 'var(--surface-overlay)',
                },
                border: {
                    DEFAULT: 'var(--border)',
                    subtle: 'var(--border-subtle)',
                },
                text: {
                    DEFAULT: 'var(--text)',
                    muted: 'var(--text-muted)',
                    subtle: 'var(--text-subtle)',
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    hover: 'var(--accent-hover)',
                    muted: 'var(--accent-muted)',
                    text: 'var(--accent-text)',
                },
                user: {
                    DEFAULT: 'var(--user-bubble)',
                    text: 'var(--user-text)',
                },
                ai: {
                    DEFAULT: 'var(--ai-bubble)',
                    text: 'var(--ai-text)',
                },
                success: {
                    DEFAULT: 'var(--success)',
                    muted: 'var(--success-muted)',
                },
                error: {
                    DEFAULT: 'var(--error)',
                    muted: 'var(--error-muted)',
                },
            },
            fontFamily: {
                display: ['Plus Jakarta Sans', 'system-ui', '-apple-system', 'sans-serif'],
                sans: ['Plus Jakarta Sans', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            animation: {
                'fade-in': 'fadeIn 0.4s ease-out',
                'slide-up': 'slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                'pulse-subtle': 'pulseSubtle 2s ease-in-out infinite',
                'warm-glow': 'warmGlow 0.6s ease-out',
                'check-draw': 'checkDraw 0.4s ease-out forwards',
                'gentle-bounce': 'gentleBounce 0.5s ease-out',
                'float': 'float 3s ease-in-out infinite',
                'vocab-highlight': 'vocabHighlight 0.3s ease-out forwards',
                'level-badge-pop': 'levelBadgePop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards',
                'progress-shimmer': 'progressShimmer 1.5s linear infinite',
                'confetti-burst': 'confettiBurst 0.4s ease-out forwards',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { opacity: '0', transform: 'translateY(12px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                pulseSubtle: {
                    '0%, 100%': { opacity: '1' },
                    '50%': { opacity: '0.6' },
                },
                warmGlow: {
                    '0%': { boxShadow: '0 0 0 0 var(--accent-muted)' },
                    '50%': { boxShadow: '0 0 20px 4px var(--accent-muted)' },
                    '100%': { boxShadow: '0 0 0 0 var(--accent-muted)' },
                },
                checkDraw: {
                    '0%': { strokeDashoffset: '24' },
                    '100%': { strokeDashoffset: '0' },
                },
                gentleBounce: {
                    '0%': { transform: 'scale(0.95)' },
                    '50%': { transform: 'scale(1.02)' },
                    '100%': { transform: 'scale(1)' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-4px)' },
                },
            },
            borderRadius: {
                '4xl': '2rem',
            },
            boxShadow: {
                'warm-sm': '0 1px 3px var(--shadow-color), 0 1px 2px var(--shadow-color)',
                'warm': '0 4px 12px var(--shadow-color), 0 2px 4px var(--shadow-color)',
                'warm-lg': '0 8px 24px var(--shadow-color), 0 4px 8px var(--shadow-color)',
                'warm-xl': '0 16px 40px var(--shadow-color), 0 8px 16px var(--shadow-color)',
                'inner-warm': 'inset 0 2px 4px var(--shadow-color)',
            },
        }
    }
};
