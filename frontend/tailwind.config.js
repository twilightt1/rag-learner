/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#eeedfe',
          100: '#d4d0fc',
          200: '#afa9ec',
          400: '#9b8de8',
          500: '#7f77dd',
          600: '#6b5fd0',
          700: '#534ab7',
          900: '#26215c',
        },
        dark: {
          base:     '#0b0d11',
          surface:  '#13161c',
          card:     '#1a1e27',
          elevated: '#222733',
          border:   '#2a2f3a',
        },
      },
      animation: {
        'fade-in':   'fadeIn 0.3s ease-out both',
        'slide-up':  'slideUp 0.4s ease-out both',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: 0, transform: 'translateY(6px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        slideUp: {
          from: { opacity: 0, transform: 'translateY(16px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
