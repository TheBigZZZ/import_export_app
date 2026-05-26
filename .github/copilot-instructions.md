# Copilot Instructions

## Stack

- Backend: FastAPI + SQLAlchemy (async) + SQLite + Alembic
- Frontend: PySide6 desktop client
- Auth: JWT with bcrypt password hashing
- Reporting stack prepared with pandas, OpenPyXL, and ReportLab

## Behavior
- If you are unsure about anything, stop and ask — don't guess.
- If something could break existing functionality, warn me before doing it.
- After finishing a task, tell me what you did and what (if anything) needs manual action
- If there are multiple ways to do something, recommend the best one and explain why briefly

## Never Do This
- Never leave TODO comments — always implement it fully right now
- Never use hardcoded values — use constants or environment variables
- Never use console.log in production code — remove after debugging
- Never use deprecated APIs or packages
- Never expose secrets or API keys in code
- Never write partial implementations — always complete the full feature
- Never break existing functionality when adding new code
- Never create a new component or file if a suitable one already exists
- Never leave dead code, unused imports, or unused variables
- Never skip error handling — always implement it fully
- Never skip loading and empty states in UI — always implement them
- Never stop mid-task to ask for clarification — make the best decision and keep going
- Never install a package without first checking if the functionality already exists in the project

## Coding Style
- Write clean, production-ready code only
- Simplest solution that works correctly and perfectly — never over-engineer
- Never use deprecated APIs or packages — always use latest stable versions
- Add comments only on complex logic, nowhere else
- Always design with perfection in mind.
- If you are ever given an error message from the user. Always check any for common problems and mistakes that may be the reason for the error. Be sincere. Dont be afraid to ask. Dont always go around trying to find a fix. The fix may be just a small change, nothing too big and overcomplicated and has to be done multiple times desperately trying.

## Workflow
- Always plan fully before writing any code
- Think through edge cases before implementing
- Execute prompts completely — never partially implement or summarize
- If manual setup is required, explain every step clearly
- Always use the best approach that balances quality, speed, and simplicity

## Testing
- Always run tests after implementing
- Ensure all tests pass before finishing
- If no tests exist, write them for critical logic

## Security
- Never expose API keys or secrets in code
- Always use environment variables for sensitive values
- Never commit .env files
- Always validate and sanitize user inputs
- Always handle authentication and authorization properly

## Error Handling
- Always handle errors explicitly — never silent catch blocks
- Always show meaningful error messages to the user
- Always handle loading and empty states in UI components
- Never assume an API call will succeed — always handle failure

## Performance
- Always think about performance — avoid unnecessary re-renders, queries, or API calls
- Never fetch data you don't need
- Use caching where it makes sense