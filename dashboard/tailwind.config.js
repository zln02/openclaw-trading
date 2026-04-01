/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  // darkMode removed: theme uses CSS custom properties, not Tailwind dark: utilities
  theme: {
    extend: {
      colors: {
        shell: "var(--bg-primary)",
        panel: "var(--bg-secondary)",
        elevated: "var(--bg-elevated)",
        border: "var(--border-default)",
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        profit: "var(--color-profit)",
        loss: "var(--color-loss)",
        warning: "var(--color-warning)",
        info: "var(--color-info)",
        btc: "var(--accent-btc)",
        kr: "var(--accent-kr)",
        us: "var(--accent-us)",
        agents: "var(--accent-agents)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        card: "var(--panel-radius)",
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
      },
    },
  },
  plugins: [],
};
