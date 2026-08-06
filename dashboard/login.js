const loginForm = document.querySelector("#login-form");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");

loginForm.addEventListener("submit", async (browserEvent) => {
    browserEvent.preventDefault();

    loginError.hidden = true;
    loginButton.disabled = true;
    loginButton.textContent = "Signing in...";

    const formData = new FormData(loginForm);

    try {
        const response = await fetch(
            "/auth/login",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    username: formData.get("username"),
                    password: formData.get("password"),
                }),
            }
        );

        if (!response.ok) {
            throw new Error("Authentication failed.");
        }

        window.location.replace("/dashboard");
    }
    catch (error) {
        console.error(error);
        loginError.hidden = false;
    }
    finally {
        loginButton.disabled = false;
        loginButton.textContent = "Sign in to Watchtower";
    }
});

if (window.performance.getEntriesByType("navigation")[0]?.type !== "reload") {
    redirectAuthenticatedUser();
}

