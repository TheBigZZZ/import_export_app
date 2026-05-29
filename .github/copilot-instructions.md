# Copilot Instructions

## Stack

- Backend: FastAPI + SQLAlchemy (async) + SQLite for local/dev, with support for a shared database URL in live mode
- Frontend: PySide6 desktop client
- Auth: JWT with bcrypt password hashing
- Live sync: Server-sent events from the backend to refresh open clients automatically
- Reporting stack prepared with pandas, OpenPyXL, and ReportLab

## Mindset
- Write production-ready code only — simple, correct, and complete. Never over-engineer.
- Plan fully and think through edge cases before writing a single line.
- Always use the best approach that balances quality, speed, and simplicity.
- If there are multiple ways to do something, recommend the best one and briefly explain why.

## Never Do This
- Never leave TODOs, placeholders, or partial implementations — always finish the full feature.
- Never hardcode values — use constants or environment variables.
- Never use deprecated APIs or packages — always use the latest stable versions.
- Never expose secrets or API keys in code. Never commit `.env` files.
- Never leave dead code, unused imports, or unused variables.
- Never silently catch errors or skip error handling.
- Never skip loading and empty states in UI components.
- Never break existing functionality when adding new code.
- Never create a new file or component if a suitable one already exists.
- Never install a package without first checking if the functionality already exists.
- Never use `console.log` in production code — remove after debugging.

## Code Quality
- Follow best practices and established patterns for the language/framework in use.
- Keep functions small, focused, and single-purpose.
- Use meaningful, descriptive names for variables, functions, and classes.
- Add comments only on complex logic — nowhere else.
- Write testable, modular code from the start.

## Error Handling & Security
- Always handle errors explicitly with meaningful messages to the user.
- Always handle API failures — never assume a call will succeed.
- Always validate and sanitize user inputs.
- Always handle authentication and authorization properly.
- Always use environment variables for sensitive values.

## Performance
- Avoid unnecessary re-renders, queries, or API calls.
- Never fetch data you don't need.
- Use caching where it makes sense.

## Testing
- Run tests after every implementation. All tests must pass before finishing.
- If no tests exist, write them for any critical logic.

## Communication
- If something could break existing functionality, warn before doing it.
- When a task is done, briefly summarize what was done and any required manual steps.
- If a request is ambiguous, make the best decision and keep going — don't stop mid-task.
- If given an error, look for the simplest root cause first before reaching for a complex fix.
- When making a non-obvious decision, briefly explain why.