# Habla Hermano API Reference

> REST API documentation for Habla Hermano conversational language learning

---

## Overview

Habla Hermano provides an HTMX-driven API that returns HTML partials for seamless UI updates. The primary endpoint processes chat messages through a LangGraph agent and returns rendered HTML including the AI response, scaffolding assistance (for A0-A1 learners), and grammar feedback.

**Base URL**: `http://localhost:8000`

**Content Type**: All POST requests use `application/x-www-form-urlencoded` (form data).

**Response Format**: HTML partials designed for HTMX integration.

---

## Authentication

All chat routes require authentication via JWT token stored in an httponly cookie (`sb-access-token`).

### GET /auth/login

Render the login page for existing users.

**Response**: Full HTML page with login form.

**Example**:
```bash
curl http://localhost:8000/auth/login
```

---

### POST /auth/login

Authenticate user with email and password.

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | User's password |

**Response**:
- Success: Sets `sb-access-token` cookie (7-day expiry), redirects to `/`
- Error: Returns error message HTML partial

**Example**:
```bash
curl -X POST http://localhost:8000/auth/login \
  -d "email=user@example.com" \
  -d "password=secretpassword"
```

---

### GET /auth/signup

Render the signup page for new users.

**Response**: Full HTML page with signup form.

---

### POST /auth/signup

Create a new user account.

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | Password (minimum 8 characters) |

**Response**:
- Success: Creates user, sets JWT cookie, redirects to `/`
- Error: Returns error message HTML partial

---

### POST /auth/logout

Clear session and logout user.

**Response**: Clears `sb-access-token` cookie, redirects to `/auth/login`

---

## Protected Endpoints

### GET /

Render the main chat interface. **Requires authentication.**

**Response**: Full HTML page with chat UI, level/language selectors, and theme toggle.

**Authentication**: Requires valid `sb-access-token` JWT cookie.

**Unauthorized**: Returns 401 with `HX-Redirect: /auth/login` header.

**Example**:
```bash
curl http://localhost:8000/
```

---

### POST /chat

Send a message and receive an AI response with optional scaffolding and grammar feedback. **Requires authentication.**

**Authentication**: Requires valid `sb-access-token` JWT cookie. Thread ID is derived from user ID (`user:{user_id}`).

#### Request

**Content-Type**: `application/x-www-form-urlencoded`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | - | User's message in the target language |
| `level` | string | No | `A1` | CEFR proficiency level: `A0`, `A1`, `A2`, `B1` |
| `language` | string | No | `es` | Target language code: `es` (Spanish), `de` (German), `fr` (French) |

**Example Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Hola, me llamo Ana" \
  -d "level=A0" \
  -d "language=es"
```

#### Response

Returns an HTML partial (`partials/message_pair.html`) containing:
- AI response bubble
- Scaffolding section (when `scaffolding.enabled` is `true`)
- Grammar feedback section (when corrections exist)

**Response Context Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| `user_message` | string | Echo of the user's submitted message |
| `ai_response` | string | Generated AI response text |
| `scaffolding` | object | Scaffolding configuration (see below) |
| `grammar_feedback` | array | List of grammar corrections |
| `new_vocabulary` | array | List of vocabulary items introduced |

---

## Data Structures

### ScaffoldingConfig

Scaffolding provides learning assistance for A0-A1 level learners. When enabled, the response includes a collapsible help section with contextual hints, a word bank, and optional sentence starters.

**Activation**: Automatically enabled for `A0` and `A1` levels via LangGraph conditional routing.

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether scaffolding is active for this response. `true` for A0-A1 levels, `false` otherwise. |
| `word_bank` | array[string] | Relevant vocabulary for forming a response. Format varies by level (see below). |
| `hint_text` | string | English guidance explaining how to respond to the AI's message. |
| `sentence_starter` | string or null | Optional partial sentence to help the learner begin their response. |
| `auto_expand` | boolean | If `true`, scaffolding section displays expanded by default. If `false`, collapsed. |

**Word Bank Format by Level**:

| Level | Format | Example |
|-------|--------|---------|
| A0 | Word with English translation in parentheses | `["hola (hello)", "me llamo (my name is)", "buenos dias (good morning)"]` |
| A1 | Word only (assumes basic vocabulary recognition) | `["hola", "me llamo", "buenos dias"]` |

**Auto-Expand Behavior**:

| Level | `auto_expand` Value | UI Behavior |
|-------|---------------------|-------------|
| A0 | `true` | Scaffolding section is expanded by default to maximize visibility |
| A1 | `false` | Scaffolding section is collapsed by default (click to expand) |

**Example ScaffoldingConfig (A0 level)**:
```json
{
  "enabled": true,
  "word_bank": ["hola (hello)", "me llamo (my name is)", "mucho gusto (nice to meet you)"],
  "hint_text": "Try introducing yourself! Say hello and tell them your name.",
  "sentence_starter": "Hola, me llamo",
  "auto_expand": true
}
```

**Example ScaffoldingConfig (A1 level)**:
```json
{
  "enabled": true,
  "word_bank": ["estoy", "bien", "cansado", "trabajo"],
  "hint_text": "Tell them how you're feeling and why.",
  "sentence_starter": null,
  "auto_expand": false
}
```

**Example ScaffoldingConfig (A2/B1 level - disabled)**:
```json
{
  "enabled": false,
  "word_bank": [],
  "hint_text": "",
  "sentence_starter": null,
  "auto_expand": false
}
```

---

### GrammarFeedback

Grammar corrections are generated by the `analyze` node for the user's last message. Corrections are filtered by level appropriateness.

| Field | Type | Description |
|-------|------|-------------|
| `original` | string | The incorrect phrase from the user's message |
| `correction` | string | The corrected version of the phrase |
| `explanation` | string | Brief, friendly explanation of the error |
| `severity` | string | Error significance: `minor`, `moderate`, or `significant` |

**Severity Levels**:

| Severity | Description | Example |
|----------|-------------|---------|
| `minor` | Small issues that don't impede understanding | Missing accent marks |
| `moderate` | Noticeable errors that may cause confusion | Gender agreement issues |
| `significant` | Errors that change meaning or are grammatically incorrect | Ser vs estar confusion |

**Example GrammarFeedback**:
```json
{
  "original": "Yo soy cansado",
  "correction": "Yo estoy cansado",
  "explanation": "For temporary states like being tired, use 'estar' instead of 'ser'.",
  "severity": "significant"
}
```

---

### VocabWord

Vocabulary items extracted from the conversation to highlight for learning.

| Field | Type | Description |
|-------|------|-------------|
| `word` | string | The word in the target language |
| `translation` | string | English translation |
| `part_of_speech` | string | Grammatical category: `noun`, `verb`, `adjective`, `adverb`, etc. |

**Example VocabWord**:
```json
{
  "word": "cansado",
  "translation": "tired",
  "part_of_speech": "adjective"
}
```

---

## Level-Specific Behavior

The `/chat` endpoint adapts its response based on the learner's CEFR level:

| Level | Scaffolding | AI Language Mix | Grammar Feedback |
|-------|-------------|-----------------|------------------|
| **A0** | Enabled (auto-expanded), translations in word bank | 80% English, 20% Spanish | Basic errors only |
| **A1** | Enabled (collapsed), words only in word bank | 50% English, 50% Spanish | Common errors |
| **A2** | Disabled | 80% Spanish, 20% English | Intermediate errors |
| **B1** | Disabled | 95%+ Spanish | All appropriate errors |

---

## HTML Template Integration

### Response Template Structure

When scaffolding is enabled, the `partials/message_pair.html` template includes the `partials/scaffold.html` partial:

```html
<!-- AI Response -->
<div class="message-enter flex justify-start mb-6">
    <div class="bg-ai rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] shadow-sm">
        <div class="text-ai-text leading-relaxed">
            {{ ai_response | safe }}
        </div>
    </div>
</div>

<!-- Scaffolding Help (collapsible) - for A0-A1 learners -->
{% if scaffolding and scaffolding.enabled %}
{% include "partials/scaffold.html" %}
{% endif %}

<!-- Grammar Feedback (collapsible) -->
{% if grammar_feedback %}
{% include "partials/grammar_feedback.html" %}
{% endif %}
```

### Scaffold Partial Features

The scaffold partial (`partials/scaffold.html`) renders:

1. **Toggle Button**: "Need help responding?" with expand/collapse functionality
2. **Hint Section**: Contextual guidance in English
3. **Word Bank**: Clickable vocabulary chips that insert text into the input field
4. **Sentence Starter**: Optional clickable prompt to pre-fill the input

**JavaScript Integration**: Word bank chips trigger `insertWord(word)` and sentence starters trigger `insertStarter(text)` to populate the chat input field.

---

## HTMX Integration

The `/chat` endpoint is designed for HTMX requests. The recommended HTMX attributes:

```html
<form hx-post="/chat"
      hx-target="#chat-container"
      hx-swap="beforeend"
      hx-indicator="#loading">
    <input type="hidden" name="level" value="A0">
    <input type="hidden" name="language" value="es">
    <input type="text" name="message" placeholder="Type your message...">
    <button type="submit">Send</button>
</form>
```

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `hx-post` | `/chat` | POST to chat endpoint |
| `hx-target` | `#chat-container` | Element to update with response |
| `hx-swap` | `beforeend` | Append new messages to container |
| `hx-indicator` | `#loading` | Show loading state during request |

---

## Error Handling

### Common Error Responses

| Status | Cause | Response |
|--------|-------|----------|
| 400 | Missing required `message` parameter | Validation error |
| 422 | Invalid form data | Unprocessable Entity |
| 500 | LangGraph or LLM error | Internal Server Error |

### Validation

The `level` parameter is validated to accept only: `A0`, `A1`, `A2`, `B1`.

The `language` parameter is validated to accept only: `es`, `de`.

---

## Example Workflow

### A0 Beginner Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=hola" \
  -d "level=A0" \
  -d "language=es"
```

**Response includes**:
- AI response: "Great job! You said 'hola' - that means 'hello'! Now let's learn your name..."
- Scaffolding (expanded by default):
  - Hint: "Try saying your name! Use 'Me llamo' followed by your name."
  - Word bank: `["me llamo (my name is)", "mucho gusto (nice to meet you)"]`
  - Sentence starter: "Me llamo"

### A1 Beginner Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Estoy cansado" \
  -d "level=A1" \
  -d "language=es"
```

**Response includes**:
- AI response: "Ah, estas cansado? Yo tambien estoy cansado..."
- Scaffolding (collapsed by default):
  - Hint: "Tell them why you're tired."
  - Word bank: `["trabajo", "mucho", "hoy", "ayer"]`
  - Sentence starter: null

### A2/B1 Conversation

**Request**:
```bash
curl -X POST http://localhost:8000/chat \
  -d "message=Ayer fui al cine con mis amigos" \
  -d "level=A2" \
  -d "language=es"
```

**Response includes**:
- AI response: "Que pelicula vieron? Me encanta ir al cine..."
- Scaffolding: `{ "enabled": false, ... }`
- Grammar feedback (if applicable)

---

## Lesson Endpoints

The lesson system provides structured learning experiences with guided steps, exercises, and progress tracking. Lessons support guest access (no authentication required) and are designed for HTMX-driven partial page updates.

### GET /lessons/

List available lessons with optional filtering by language and level.

**Authentication**: Optional. Guest users can browse and play lessons.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `language` | string | No | - | Filter by target language code: `es`, `de`, `fr` |
| `level` | string | No | - | Filter by CEFR level: `A0`, `A1`, `A2`, `B1` |

**Response**: Full HTML page with lesson cards grid.

**Example**:
```bash
# List all lessons
curl http://localhost:8000/lessons/

# Filter by Spanish A1 lessons
curl "http://localhost:8000/lessons/?language=es&level=A1"
```

---

### GET /lessons/{lesson_id}/play

Render the lesson player page for a specific lesson.

**Authentication**: Optional. Guest users can play lessons.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: Full HTML page with lesson player interface including:
- Lesson title and description
- Progress indicator
- Step content area
- Navigation controls

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/play
```

---

### GET /lessons/{lesson_id}/step/{step_index}

Get a specific lesson step content as an HTML partial.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `step_index` | integer | Zero-based step index |

**Response**: HTML partial (`partials/lesson_step.html`) containing:
- Step instruction text
- Example content (if applicable)
- Exercise component (if step includes exercise)
- Navigation buttons

**HTMX Integration**:
```html
<div hx-get="/lessons/spanish-greetings-a0/step/0"
     hx-trigger="load"
     hx-target="#step-content">
</div>
```

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/step/0
```

---

### POST /lessons/{lesson_id}/step/next

Navigate to the next step in the lesson.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_step` | integer | Yes | Current step index |

**Response**: HTML partial for the next step, or completion partial if at end.

**Response Headers**:
- `HX-Trigger`: `stepChanged` event for progress bar updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/step/next \
  -d "current_step=0"
```

---

### POST /lessons/{lesson_id}/step/prev

Navigate to the previous step in the lesson.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_step` | integer | Yes | Current step index |

**Response**: HTML partial for the previous step.

**Response Headers**:
- `HX-Trigger`: `stepChanged` event for progress bar updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/step/prev \
  -d "current_step=2"
```

---

### GET /lessons/{lesson_id}/exercise/{exercise_id}

Get a specific exercise component as an HTML partial.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `exercise_id` | string | Unique exercise identifier within the lesson |

**Response**: HTML partial (`partials/exercise.html`) containing the exercise UI based on type:
- Multiple choice options
- Fill-in-the-blank input
- Matching pairs interface
- Audio response recorder

**Example**:
```bash
curl http://localhost:8000/lessons/spanish-greetings-a0/exercise/greeting-choice-1
```

---

### POST /lessons/{lesson_id}/exercise/{exercise_id}/submit

Submit an answer for an exercise.

**Authentication**: Optional.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |
| `exercise_id` | string | Unique exercise identifier |

**Request Body** (form data):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `answer` | string | Yes | User's submitted answer |

**Response**: HTML partial (`partials/exercise_result.html`) containing:
- Correct/incorrect indicator
- Feedback message
- Correct answer (if incorrect)
- Continue button

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/exercise/greeting-choice-1/submit \
  -d "answer=hola"
```

**Response Example (correct)**:
```html
<div class="exercise-result correct">
  <span class="icon">✓</span>
  <p class="feedback">Excellent! "Hola" is the standard greeting.</p>
  <button hx-post="/lessons/spanish-greetings-a0/step/next">Continue</button>
</div>
```

**Response Example (incorrect)**:
```html
<div class="exercise-result incorrect">
  <span class="icon">✗</span>
  <p class="feedback">Not quite. The correct answer is "hola".</p>
  <button hx-get="/lessons/spanish-greetings-a0/exercise/greeting-choice-1">Try Again</button>
</div>
```

---

### POST /lessons/{lesson_id}/complete

Mark a lesson as complete. For authenticated users, this records progress in the database.

**Authentication**: Optional. Progress is only persisted for authenticated users.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: HTML partial (`partials/lesson_complete.html`) containing:
- Completion celebration
- Summary statistics (exercises completed, accuracy)
- Recommended next lessons
- Handoff to chat option

**Response Headers**:
- `HX-Trigger`: `lessonComplete` event for UI updates

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/complete
```

---

### POST /lessons/{lesson_id}/handoff

Transition from lesson to free chat practice with lesson context.

**Authentication**: Required. The chat requires authentication for conversation persistence.

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `lesson_id` | string | Unique lesson identifier |

**Response**: Redirects to chat with lesson context pre-loaded.

**Response Headers**:
- `HX-Redirect`: `/` with lesson context query parameters

**Behavior**:
1. Validates user authentication
2. Prepares chat context with lesson vocabulary and topics
3. Sets initial chat prompt based on lesson theme
4. Redirects to main chat interface

**Example**:
```bash
curl -X POST http://localhost:8000/lessons/spanish-greetings-a0/handoff \
  --cookie "sb-access-token=<jwt_token>"
```

**Unauthenticated Response**:
```html
<!-- Returns login prompt partial -->
<div class="auth-prompt">
  <p>Sign in to continue practicing in chat mode.</p>
  <a href="/auth/login" class="btn-primary">Sign In</a>
</div>
```

---

## Lesson Data Structures

### LessonMetadata

Metadata describing a lesson for listing and filtering.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique lesson identifier (URL-safe slug) |
| `title` | string | Display title of the lesson |
| `description` | string | Brief description of lesson content |
| `language` | string | Target language code: `es`, `de`, `fr` |
| `level` | string | CEFR proficiency level: `A0`, `A1`, `A2`, `B1` |
| `duration_minutes` | integer | Estimated completion time in minutes |
| `step_count` | integer | Total number of steps in the lesson |
| `topics` | array[string] | Learning topics covered (e.g., `["greetings", "introductions"]`) |
| `thumbnail_url` | string | URL to lesson thumbnail image |

**Example LessonMetadata**:
```json
{
  "id": "spanish-greetings-a0",
  "title": "Basic Greetings",
  "description": "Learn to say hello and introduce yourself in Spanish.",
  "language": "es",
  "level": "A0",
  "duration_minutes": 10,
  "step_count": 5,
  "topics": ["greetings", "introductions", "basic phrases"],
  "thumbnail_url": "/static/lessons/thumbnails/greetings.png"
}
```

---

### LessonStep

A single step within a lesson.

| Field | Type | Description |
|-------|------|-------------|
| `index` | integer | Zero-based position in the lesson |
| `type` | string | Step type: `instruction`, `example`, `exercise`, `summary` |
| `content` | string | Main text content (supports Markdown) |
| `audio_url` | string or null | URL to audio pronunciation (if applicable) |
| `exercise` | Exercise or null | Exercise component (if type is `exercise`) |
| `vocabulary` | array[VocabWord] | Vocabulary introduced in this step |

**Example LessonStep (instruction type)**:
```json
{
  "index": 0,
  "type": "instruction",
  "content": "In Spanish, 'hola' is the most common way to say hello. It can be used in both formal and informal situations.",
  "audio_url": "/static/audio/es/hola.mp3",
  "exercise": null,
  "vocabulary": [
    {
      "word": "hola",
      "translation": "hello",
      "part_of_speech": "interjection"
    }
  ]
}
```

**Example LessonStep (exercise type)**:
```json
{
  "index": 2,
  "type": "exercise",
  "content": "Choose the correct greeting for the morning:",
  "audio_url": null,
  "exercise": {
    "id": "morning-greeting-mc",
    "type": "multiple_choice",
    "question": "How do you say 'good morning' in Spanish?",
    "options": ["Buenos dias", "Buenas noches", "Buenas tardes", "Hola"],
    "correct_answer": "Buenos dias",
    "feedback": {
      "correct": "Excellent! 'Buenos dias' is used until around noon.",
      "incorrect": "Not quite. 'Buenos dias' means 'good morning'."
    }
  },
  "vocabulary": []
}
```

---

### Exercise Types

Lessons support multiple exercise types, each with specific data structures.

#### Multiple Choice

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `multiple_choice` |
| `question` | string | Question text |
| `options` | array[string] | Answer choices (2-4 options) |
| `correct_answer` | string | The correct option |
| `feedback` | object | Feedback messages for correct/incorrect |

**Example**:
```json
{
  "id": "greeting-mc-1",
  "type": "multiple_choice",
  "question": "Which greeting is appropriate for the evening?",
  "options": ["Buenos dias", "Buenas tardes", "Buenas noches"],
  "correct_answer": "Buenas noches",
  "feedback": {
    "correct": "Correct! 'Buenas noches' is used in the evening and night.",
    "incorrect": "Remember, 'noches' means 'nights', so 'Buenas noches' is for evening."
  }
}
```

#### Fill in the Blank

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `fill_blank` |
| `sentence` | string | Sentence with `___` placeholder |
| `correct_answer` | string | Expected answer |
| `acceptable_answers` | array[string] | Alternative correct answers |
| `hint` | string | Optional hint text |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "intro-fill-1",
  "type": "fill_blank",
  "sentence": "Me ___ Maria.",
  "correct_answer": "llamo",
  "acceptable_answers": ["llamo"],
  "hint": "This verb means 'to call oneself'",
  "feedback": {
    "correct": "Perfect! 'Me llamo' means 'I am called' or 'My name is'.",
    "incorrect": "The answer is 'llamo'. 'Me llamo' literally means 'I call myself'."
  }
}
```

#### Matching

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `matching` |
| `instruction` | string | Exercise instruction |
| `pairs` | array[object] | Array of `{left, right}` pairs to match |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "greetings-match-1",
  "type": "matching",
  "instruction": "Match the Spanish greeting with its English meaning:",
  "pairs": [
    {"left": "Hola", "right": "Hello"},
    {"left": "Buenos dias", "right": "Good morning"},
    {"left": "Buenas noches", "right": "Good night"},
    {"left": "Adios", "right": "Goodbye"}
  ],
  "feedback": {
    "correct": "Excellent! You matched all the greetings correctly.",
    "incorrect": "Some matches were incorrect. Review and try again."
  }
}
```

#### Audio Response

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique exercise identifier |
| `type` | string | Always `audio_response` |
| `prompt` | string | What the user should say |
| `expected_phrase` | string | Expected spoken phrase |
| `audio_example_url` | string | URL to example pronunciation |
| `feedback` | object | Feedback messages |

**Example**:
```json
{
  "id": "pronunciation-1",
  "type": "audio_response",
  "prompt": "Say 'Mucho gusto' (Nice to meet you)",
  "expected_phrase": "Mucho gusto",
  "audio_example_url": "/static/audio/es/mucho-gusto.mp3",
  "feedback": {
    "correct": "Great pronunciation! 'Mucho gusto' is perfect for introductions.",
    "incorrect": "Try again. Listen to the example and match the pronunciation."
  }
}
```

---

## Lesson HTMX Integration

### Lesson Player Structure

```html
<div id="lesson-player">
  <!-- Progress bar -->
  <div id="progress-bar"
       hx-get="/lessons/spanish-greetings-a0/progress"
       hx-trigger="stepChanged from:body">
    <div class="progress" style="width: 20%"></div>
  </div>

  <!-- Step content area -->
  <div id="step-content"
       hx-get="/lessons/spanish-greetings-a0/step/0"
       hx-trigger="load">
  </div>

  <!-- Navigation -->
  <div id="lesson-nav">
    <button hx-post="/lessons/spanish-greetings-a0/step/prev"
            hx-target="#step-content"
            hx-include="[name='current_step']">
      Previous
    </button>
    <button hx-post="/lessons/spanish-greetings-a0/step/next"
            hx-target="#step-content"
            hx-include="[name='current_step']">
      Next
    </button>
  </div>
</div>
```

### Exercise Submission

```html
<form hx-post="/lessons/spanish-greetings-a0/exercise/greeting-mc-1/submit"
      hx-target="#exercise-result"
      hx-swap="innerHTML">
  <input type="hidden" name="answer" id="selected-answer">
  <div class="options">
    <button type="button" onclick="selectOption('hola')">Hola</button>
    <button type="button" onclick="selectOption('adios')">Adios</button>
  </div>
  <button type="submit">Check Answer</button>
</form>
<div id="exercise-result"></div>
```

---

## Related Documentation

- [Product Specification](./product.md) - Vision, pedagogy, and feature details
- [Technical Architecture](./architecture.md) - LangGraph design and implementation phases
- [E2E Test Results](./playwright-e2e.md) - Playwright testing documentation
