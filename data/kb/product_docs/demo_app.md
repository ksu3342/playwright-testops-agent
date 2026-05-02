# Demo App Product Notes

## Login
- Page URL: `/login`
- A valid user enters email and password, submits the form, and lands on the dashboard.
- The dashboard heading is the visible success signal for the happy path.
- Invalid credentials should keep the user on the login page and show an inline error.

## Search
- Page URL: `/search`
- A user enters a keyword, submits the search form, and sees matching result items.
- A no-match keyword should show the empty state instead of result items.
