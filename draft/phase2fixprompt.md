
---

> **Bug Fix Request: Phase 2 UI Improvements & Interactions**
> Please fix the following 4 UI issues in `rag-ui`:
> 1. **Theme Toggle & Soft Eye-Saving Light Mode:**
> * Add a theme toggle switch (Sun/Moon icon) in the header.
> * Support both Dark and Light mode.
> * For Light Mode, **do not use harsh pure white (`#ffffff`)**. Use eye-friendly soft pastel slate/warm gray tones  like reading on paper (warm cream/soft slate tones instead of glaring white).
> 
> 2. **Mobile Sidebar Functionality:**
> * Add a Mobile Hamburger Menu toggle button in the header (visible on `sm`/`md` screens).
> * Render the sidebar in a slide-out overlay/drawer on mobile viewports.
> * Ensure mobile drawer event handlers correctly trigger like desktop version:
> * Opening and closing the sidebar overlay.
> * Creating a **+ New Chat** session.
> * Selecting different chat sessions from history.
> * Clicking **← Switch Subject** to return to the Subject Hub.
> * Clicking **Logout** (auto-close sidebar on click).
> 
> 
> 
> 
> 3. **Smooth Scroll & Manual Scroll Control During AI Streaming:**
> * Fix auto-scrolling during text generation so it doesn't lock the viewport.
> * Auto-scroll to the bottom *only* if the user is already at the bottom of the chat container.
> * Allow the user to scroll up freely to read earlier text while the response is streaming without snapping back down continuously.
> 
> 
> 4. **General Interactive Edge Cases:**
> * Ensure active state handlers (`activeSubject`, `activeSessionId`, `currentUser`) in `useWorkspaceStore` correctly sync across both mobile and desktop viewports.
> 
> 
> 
> 

---
