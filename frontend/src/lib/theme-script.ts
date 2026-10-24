export const THEME_KEY = "gitmore-theme";

// Runs before the page paints (see app/layout.tsx), so a saved theme never flashes.
// Kept apart from theme.ts, which uses React hooks the server layout can't import.
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
