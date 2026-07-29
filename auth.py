from bs4 import BeautifulSoup
from httpx import Client


def authenticate(roll: str, password: str, LOGIN_URL, ROUTINE_URL) -> Client:
    client = Client(follow_redirects=True)
    print("Authenticating...")

    # Fetch login page
    response = client.get(LOGIN_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the login form containing the roll and password fields
    form = next(
        (
            form
            for form in soup.find_all("form")
            if form.find("input", {"name": "roll"})
            and form.find("input", {"name": "password"})
        ),
        None,
    )

    if form is None:
        raise RuntimeError("The portal login form was not found.")

    token = form.find("input", {"name": "_token"})
    if token is None or not token.get("value"):
        raise RuntimeError("The CSRF token was not found.")

    payload = {
        "_token": token["value"],
        "roll": roll,
        "password": password,
    }

    # Submit login form
    response = client.post(
        LOGIN_URL,
        data=payload,
        headers={"Referer": LOGIN_URL},
    )
    response.raise_for_status()

    return client
