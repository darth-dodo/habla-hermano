# Add HTMX Template

Create or modify Jinja2 + HTMX templates for the frontend.

## When to Use
- Adding a new page to the web application
- Creating HTMX partial templates for dynamic content
- Modifying existing UI components (chat, lessons, review, progress)

## Steps

1. **Review existing template patterns**
   - Read templates in `src/templates/` for layout and component patterns
   - Read `src/static/css/input.css` for Tailwind custom styles
   - Read `src/static/js/` for Alpine.js and HTMX handler patterns

2. **Create the template** at `src/templates/{name}.html`

   **Full page template** (extends base layout):
   ```html
   {% extends "base.html" %}

   {% block title %}{Page Title} - Habla Hermano{% endblock %}

   {% block content %}
   <div class="container mx-auto px-4 py-6 max-w-2xl">
     <h1 class="text-2xl font-bold mb-4">{Title}</h1>
     <!-- Content here -->
   </div>
   {% endblock %}
   ```

   **HTMX partial** (for dynamic swaps):
   ```html
   <div id="{target-id}" class="...">
     <!-- Content that gets swapped in -->
   </div>
   ```

3. **HTMX interaction patterns**
   ```html
   <!-- POST with form data, swap inner content -->
   <form hx-post="/api/endpoint" hx-target="#result" hx-swap="innerHTML">
     <input type="text" name="message" />
     <button type="submit">Send</button>
   </form>

   <!-- GET to load content -->
   <div hx-get="/api/data" hx-trigger="load" hx-target="#container">
     Loading...
   </div>

   <!-- Click to navigate steps -->
   <button hx-post="/lessons/{{ lesson_id }}/step/next"
           hx-target="#step-content"
           hx-swap="innerHTML">
     Next
   </button>
   ```

4. **Mobile-responsive design rules**
   - Mobile-first: start with small screen, add `md:` and `lg:` breakpoints
   - Touch targets: minimum 48px (`min-h-[48px] min-w-[48px]`)
   - Safe areas: use `pt-[var(--safe-top)]` for notched phones
   - Single column on mobile, multi-column on desktop

5. **Theme support** (3 themes: light, dark, ocean)
   - Use CSS variables for theme-aware colors
   - Use `dark:` Tailwind prefix for dark mode variants
   - Theme toggle handled by Alpine.js in base template

6. **Create the route** to serve the template (see `add-api-route` skill)

7. **Compile Tailwind CSS** after adding new utility classes:
   ```bash
   npx tailwindcss -i ./src/static/css/input.css -o ./src/static/css/output.css
   ```

8. **Test the template**
   - Verify route returns 200 with correct content type
   - Test HTMX interactions work correctly
   - Check responsive behavior at different viewport sizes

## Tech Stack
- **Jinja2**: Server-side templating with `{{ variable }}` and `{% block %}` syntax
- **HTMX**: Dynamic content via `hx-*` attributes (no full page reloads)
- **Alpine.js**: Client-side reactivity via `x-data`, `x-show`, `@click`
- **Tailwind CSS**: Utility-first styling, compiled from `input.css`

## File Organization
| File | Purpose |
|------|---------|
| `src/templates/base.html` | Base layout with nav, footer, theme support |
| `src/templates/chat.html` | Main chat interface |
| `src/templates/lessons/` | Lesson catalog, player, exercises |
| `src/templates/review.html` | Spaced repetition review interface |
| `src/templates/progress.html` | Learning progress dashboard |
| `src/static/css/input.css` | Tailwind input with custom styles |
| `src/static/css/output.css` | Compiled Tailwind output (gitignored) |
| `src/static/js/` | Alpine.js components, HTMX handlers |
