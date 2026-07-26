/** @type {import('tailwindcss').Config} */
const tokenColor = (name) => `rgb(var(--ds-${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: tokenColor('surface-base'),
          DEFAULT: tokenColor('surface'),
          raised: tokenColor('surface-raised'),
          hover: tokenColor('surface-hover'),
          active: tokenColor('surface-active'),
          overlay: tokenColor('surface-overlay'),
          inverse: tokenColor('surface-inverse'),
        },
        primary: {
          DEFAULT: tokenColor('primary'),
          hover: tokenColor('primary-hover'),
          active: tokenColor('primary-active'),
          subtle: 'var(--primary-subtle)',
        },
        success: { DEFAULT: tokenColor('success'), hover: 'var(--success-hover)', subtle: 'var(--success-subtle)' },
        warning: { DEFAULT: tokenColor('warning'), hover: 'var(--warning-hover)', subtle: 'var(--warning-subtle)' },
        danger: { DEFAULT: tokenColor('danger'), hover: 'var(--danger-hover)', subtle: 'var(--danger-subtle)' },
        info: { DEFAULT: tokenColor('info'), hover: 'var(--info-hover)', subtle: 'var(--info-subtle)' },
        accent: { DEFAULT: tokenColor('accent'), hover: 'var(--accent-hover)', subtle: 'var(--accent-subtle)' },
        content: {
          primary: tokenColor('text-primary'),
          secondary: tokenColor('text-secondary'),
          muted: tokenColor('text-muted'),
          inverse: tokenColor('text-inverse'),
          'on-primary': tokenColor('text-on-primary'),
        },
        line: {
          DEFAULT: tokenColor('border'),
          strong: tokenColor('border-strong'),
          focus: tokenColor('focus'),
        },
        selected: { DEFAULT: 'var(--selected)', strong: 'var(--selected-strong)' },
        disabled: 'var(--disabled-surface)',
        chart: {
          1: tokenColor('chart-1'), 2: tokenColor('chart-2'), 3: tokenColor('chart-3'),
          4: tokenColor('chart-4'), 5: tokenColor('chart-5'), 6: tokenColor('chart-6'),
        },
      },
      fontFamily: {
        sans: ['var(--font-body)'],
        heading: ['var(--font-heading)'],
        mono: ['var(--font-mono)'],
        tibia: ['var(--font-heading)'],
      },
      borderRadius: {
        sm: 'var(--radius-sm)', md: 'var(--radius-md)', lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)', '2xl': 'var(--radius-2xl)', full: 'var(--radius-full)',
      },
      boxShadow: {
        sm: 'var(--elevation-1)', DEFAULT: 'var(--elevation-2)', lg: 'var(--elevation-3)', overlay: 'var(--elevation-overlay)',
      },
      transitionDuration: {
        fast: 'var(--duration-fast)', base: 'var(--duration-base)', slow: 'var(--duration-slow)',
      },
      transitionTimingFunction: {
        standard: 'var(--ease-standard)', emphasized: 'var(--ease-emphasized)',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-in-up': { from: { opacity: '0', transform: 'translateY(var(--space-2))' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      animation: {
        'fade-in': 'fade-in var(--duration-slow) var(--ease-emphasized) both',
        'fade-in-up': 'fade-in-up var(--duration-slow) var(--ease-emphasized) both',
        in: 'fade-in var(--duration-slow) var(--ease-emphasized) both',
      },
      zIndex: {
        base: 'var(--z-base)', dropdown: 'var(--z-dropdown)', sticky: 'var(--z-sticky)', overlay: 'var(--z-overlay)', modal: 'var(--z-modal)', toast: 'var(--z-toast)', tooltip: 'var(--z-tooltip)',
      },
    },
  },
  plugins: [],
};
